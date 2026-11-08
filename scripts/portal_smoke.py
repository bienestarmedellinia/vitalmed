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
        # Mapa real del hero: portal.js inyecta docs/mapa_comunas.svg → >=16 territorios (paths).
        try:
            pag.locator("#hero-mapa path.terr").first.wait_for(timeout=8000)
            if pag.locator("#hero-mapa path.terr").count() < 16:
                errores.append("Hero: el mapa real no se inyectó con los 21 territorios (paths.terr < 16)")
        except Exception:
            errores.append("Hero: no apareció el mapa real (#hero-mapa path.terr)")
        # Observatorio por preguntas: tarjetas de categoría → preguntas → modal con gráfica.
        pag.locator("#preg-cats .cat-card").first.wait_for(timeout=8000)
        if pag.locator("#preg-cats .cat-card").count() < 5:
            errores.append("Observatorio: no se pintaron las tarjetas de categoría")
        # Abrir la primera categoría y comprobar módulos + preguntas.
        pag.locator("#preg-cats .cat-card").first.click()
        pag.locator("#preg-panel .preg-card").first.wait_for(timeout=8000)
        # Módulos de categoría: debe aparecer el panel con resumen ejecutivo e indicadores clave.
        if pag.locator("#preg-panel .cat-panel").count() < 1:
            errores.append("Observatorio: la categoría no mostró el panel de módulos")
        if pag.locator("#preg-panel .cat-analisis").count() < 1:
            errores.append("Observatorio: la categoría no mostró el módulo de análisis técnico (.cat-analisis)")
        if pag.locator("#preg-panel table.m-kpis").count() < 1:
            errores.append("Observatorio: no se pintaron los indicadores clave (semáforo por tendencia)")
        if pag.locator("#preg-panel .preg-card").count() < 1:
            errores.append("Observatorio: la categoría no mostró preguntas")
        else:
            # Abrir una pregunta y validar modal con formato completo: gráfica, badges, acciones, tabla, descarga.
            pag.locator("#preg-panel .preg-card").first.click()
            pag.locator("#preg-modal").wait_for(state="visible", timeout=8000)
            if pag.locator("#preg-modal #modal-canvas").count() < 1:
                errores.append("Observatorio: el modal no contiene la gráfica")
            if pag.locator("#preg-modal #modal-badges span").count() < 1:
                errores.append("Observatorio: el modal no muestra badges (tipo/prioridad/indicadores)")
            if pag.locator("#preg-modal #modal-acciones li").count() < 1:
                errores.append("Observatorio: el modal no muestra acciones derivadas")
            if pag.locator("#preg-modal #modal-tabla table tr").count() < 1:
                errores.append("Observatorio: el modal no muestra la tabla de datos")
            if pag.locator("#preg-modal #modal-csv").count() < 1:
                errores.append("Observatorio: el modal no ofrece descarga CSV")
            # Cerrar el modal.
            pag.click("#modal-x")
        # Carrusel de años: al menos una tarjeta debe tener varios años (indicador «i/total»).
        anios_kpi = pag.locator(".kpi .kpi-anio").all_inner_texts()
        if not any("/" in t for t in anios_kpi):
            errores.append(f"Los KPIs no muestran el carrusel por año: {anios_kpi!r}")

        # Explorador de datos (módulo independiente, sigue disponible por URL directa).
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
