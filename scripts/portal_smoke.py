#!/usr/bin/env python3
"""
portal_smoke.py — Prueba de humo del portal (docs/) en un Chromium real.

Sirve docs/ en localhost, abre la página y FALLA si:
  - hay errores de JavaScript o violaciones de la Content-Security-Policy,
  - Chart.js no carga (p. ej. hash SRI incorrecto),
  - el portal no pinta sus KPIs o el asistente no responde.

Corre en GitHub Actions (workflow portal.yml), NO en la Raspberry Pi.
Uso local (con playwright instalado):  python scripts/portal_smoke.py
"""
from __future__ import annotations
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent.parent / "docs"
PREGUNTA = "¿qué tan grave está la situación en el centro?"   # el motor solo NO la entiende
# El Worker real rechaza el origen localhost; en la prueba se simula su respuesta
# (mismo contrato que worker/src/index.js) para probar el camino con IA.
IA_SIMULADA = {"intencion": "territorio", "territorios": ["La Candelaria"], "indicador": "mortalidad",
               "anios": [], "causa": False}


def main() -> int:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"

    errores: list[str] = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pag = nav.new_page()
        pag.on("pageerror", lambda e: errores.append(f"JS: {e}"))
        pag.on("console", lambda m: m.type == "error" and errores.append(f"consola: {m.text}"))
        pag.route("**/interpretar", lambda ruta: ruta.fulfill(
            status=200, content_type="application/json", body=json.dumps(IA_SIMULADA),
            headers={"Access-Control-Allow-Origin": "*"}))
        pag.goto(url, wait_until="networkidle")

        if not pag.evaluate("typeof window.Chart === 'function'"):
            errores.append("Chart.js no cargó (¿hash SRI o CSP?)")
        kpis = pag.locator("#kpis > *").count()
        if kpis == 0:
            errores.append("El portal no pintó los KPIs (¿falló portal.js o el KB?)")
        # Observatorio por preguntas: tarjetas de categoría → preguntas → modal con gráfica.
        pag.locator("#preg-cats .cat-card").first.wait_for(timeout=8000)
        if pag.locator("#preg-cats .cat-card").count() < 5:
            errores.append("Observatorio: no se pintaron las tarjetas de categoría")
        # Abrir la primera categoría y comprobar que lista preguntas.
        pag.locator("#preg-cats .cat-card").first.click()
        pag.locator("#preg-panel .preg-card").first.wait_for(timeout=8000)
        if pag.locator("#preg-panel .preg-card").count() < 1:
            errores.append("Observatorio: la categoría no mostró preguntas")
        else:
            # Abrir una pregunta y validar que el modal aparece con un canvas dibujado.
            pag.locator("#preg-panel .preg-card").first.click()
            pag.locator("#preg-modal").wait_for(state="visible", timeout=8000)
            if pag.locator("#preg-modal #modal-canvas").count() < 1:
                errores.append("Observatorio: el modal no contiene la gráfica")
            # Cerrar el modal.
            pag.click("#modal-x")
        # Carrusel de años: al menos una tarjeta debe tener varios años (indicador «i/total»).
        anios_kpi = pag.locator(".kpi .kpi-anio").all_inner_texts()
        if not any("/" in t for t in anios_kpi):
            errores.append(f"Los KPIs no muestran el carrusel por año: {anios_kpi!r}")

        pag.fill("#q", PREGUNTA)
        pag.click("#btn-preguntar")
        pag.wait_for_function("!document.querySelector('#resp').innerText.includes('Interpretando')",
                              timeout=15000)
        resp = pag.locator("#resp").inner_text()
        if "La Candelaria" not in resp or "1325.6" not in resp:
            errores.append(f"El asistente no respondió como se esperaba: {resp[:120]!r}")
        if "Interpreté tu pregunta con IA" not in resp:
            errores.append("No se usó (o no se declaró) la interpretación con IA")
        if pag.input_value("#q") != "":
            errores.append("El campo de pregunta no se limpió")

        # Botón sugerido de ayuda (solo motor, sin IA) y gráfico de varias series.
        pag.get_by_role("button", name="¿Qué preguntas puedo hacer?").click()
        ayuda = pag.locator("#resp").inner_text()
        if "Ejemplos" not in ayuda:
            errores.append(f"La ayuda no respondió: {ayuda[:120]!r}")
        pag.get_by_role("button", name="¿Cómo varió la mortalidad entre 2012 y 2022?").click()
        n_series = pag.evaluate("Chart.getChart('chart') ? Chart.getChart('chart').data.datasets.length : 0")
        if n_series < 2:
            errores.append(f"La tendencia debería mostrar territorio + Medellín (series: {n_series})")
        # Explorador de datos (módulo independiente del asistente).
        pag2 = nav.new_page()
        pag2.on("pageerror", lambda e: errores.append(f"datos.html JS: {e}"))
        pag2.on("console", lambda m: m.type == "error" and errores.append(f"datos.html consola: {m.text}"))
        pag2.goto(url + "datos.html#ind=dengue&anio=2016&terr=7", wait_until="networkidle")
        filas = pag2.locator("#t-rank tbody tr").count()
        if filas < 21:
            errores.append(f"Explorador: la tabla del indicador tiene {filas} filas (esperadas >= 21)")
        if "Dengue" not in pag2.locator("#t-rank caption").inner_text().capitalize():
            errores.append("Explorador: no respetó el indicador del enlace (#ind=dengue)")
        if pag2.locator("#lista-desc li").count() < 2:
            errores.append("Explorador: no listó las descargas de docs/datos/")
        # Sección nueva: Salud en el tiempo (DANE/SIVIGILA/RIPS).
        if pag2.locator("#ct-serie option").count() < 1:
            errores.append("Explorador: la sección 'Salud en el tiempo' no listó series")
        if not pag2.evaluate("Chart.getChart('c-ct') && Chart.getChart('c-ct').data.labels.length > 0"):
            errores.append("Explorador: la serie temporal de ciudad (c-ct) no pintó")
        if pag2.evaluate("typeof window.Asistente") != "undefined":
            errores.append("Explorador: no debe cargar el asistente (módulos separados)")
        nav.close()
    srv.shutdown()

    if errores:
        print("PORTAL: FALLÓ")
        for e in errores:
            print("  ✗", e)
        return 1
    print(f"PORTAL: OK ({kpis} KPIs, asistente + IA simulada responden, explorador de datos OK, sin errores JS/CSP)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
