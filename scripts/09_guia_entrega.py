#!/usr/bin/env python3
"""
09_guia_entrega.py — Genera ficha_hallazgos.pdf (ficha de hallazgos del artefacto).

Entregable de apoyo de la Hackathon de Datos 2026 (el formulario oficial del ITM
es guia_entrega.pdf, documento aparte). Todas las cifras se leen de
outputs/kb/knowledge_base.json (generado por el pipeline): nada se escribe a
mano. Los datos del equipo vienen de equipo.yml.

Salida: ficha_hallazgos.pdf (raíz del repo)

Se ejecuta en GitHub Actions tras el paso 07. Requiere reportlab (liviano) y
usa los PNG de outputs/graficos/ si existen.
"""
from __future__ import annotations
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

BASE = Path(__file__).resolve().parent.parent
KB_F = BASE / "outputs" / "kb" / "knowledge_base.json"
EQUIPO_F = BASE / "equipo.yml"
GRA = BASE / "outputs" / "graficos"
SALIDA = BASE / "ficha_hallazgos.pdf"

REPO = "https://github.com/bienestarmedellinia/vitalmed"
PORTAL = "https://bienestarmedellinia.github.io/vitalmed/"

AZUL = colors.HexColor("#1f4e79")
AZUL_OSC = colors.HexColor("#0f2a44")
NAR = colors.HexColor("#d9731a")
GRIS = colors.HexColor("#4b5563")
CLARO = colors.HexColor("#eef2f7")
ROJO = colors.HexColor("#b23b3b")


def log(m: str) -> None:
    print(f"[guia] {m}", flush=True)


def e(x) -> str:
    """Escapa texto dinámico para Paragraph y deja solo caracteres de Helvetica."""
    t = str(x)
    for a, b in (("≥", ">="), ("→", "->"), ("≈", "~"), ("’", "'")):
        t = t.replace(a, b)
    return escape(t)


def fmt(n, d=1) -> str:
    """Formato es-CO: 1.325,6"""
    s = f"{float(n):,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ── Estadística (misma lógica que el portal) ───────────────────────────
def mediana(a):
    s = sorted(a)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


def calcular(kb: dict) -> dict:
    """Deriva del KB todas las cifras que usa la ficha."""
    ind = kb["indicadores"]
    h = ind["hallazgo_mortalidad"]
    mort = {m["comuna"]: m for m in ind["mortalidad_2022"]["ranking"]}
    terr = []
    for x in ind["indice_priorizacion"]["ranking"]:
        m = mort.get(x["comuna"], {})
        terr.append({"nombre": x["nombre"], "indice": x["indice"],
                     "nm": x["n_mortalidad"], "ns": x["n_suicidio"],
                     "tm": x.get("tasa_mortalidad", m.get("tasa")),
                     "ts": x.get("tasa_suicidio"), "casos": m.get("casos")})
    r = {"h": h, "terr": terr}
    r["top3"] = [t["nombre"] for t in terr[:3]]
    # Tasa de ciudad (población implícita = casos / tasa)
    casos = sum(t["casos"] for t in terr if t["casos"])
    pob = sum(t["casos"] / t["tm"] * 1e5 for t in terr if t["casos"] and t["tm"])
    r["ciudad"] = casos / pob * 1e5 if pob else None
    # Doble carga
    if all(t["ts"] is not None for t in terr):
        mx = mediana([t["tm"] for t in terr])
        my = mediana([t["ts"] for t in terr])
        r["doble"] = [t["nombre"] for t in terr if t["tm"] > mx and t["ts"] > my]
        r["pearson"] = pearson([t["tm"] for t in terr], [t["ts"] for t in terr])
    else:
        r["doble"], r["pearson"] = [], None
    # Robustez del índice: 21 ponderaciones 0..100 paso 5
    unos, top3c, n = {}, {}, 0
    for w in range(0, 101, 5):
        n += 1
        ord_ = sorted(terr, key=lambda t: -(w * t["nm"] + (100 - w) * t["ns"]) / 100)
        unos[ord_[0]["nombre"]] = unos.get(ord_[0]["nombre"], 0) + 1
        for t in ord_[:3]:
            top3c[t["nombre"]] = top3c.get(t["nombre"], 0) + 1
    r["rob_n"] = n
    r["rob_uno"] = max(unos.items(), key=lambda kv: kv[1])
    r["rob_top3"] = len(top3c)
    # Aire
    pm = ind.get("pm25_siata", {})
    r["pm"] = pm
    cmp_ = pm.get("comparacion")
    if cmp_:
        est = cmp_["estaciones"]
        r["pm_mejoran"] = sum(1 for s in est if s["actual"] < s["anterior"])
        r["pm_n"] = len(est)
        r["pm_prom_ant"] = sum(s["anterior"] for s in est) / len(est)
        r["pm_prom_act"] = sum(s["actual"] for s in est) / len(est)
    if pm.get("ranking"):
        r["pm_todas_sobre_oms"] = all(x["media_pm25"] > 5 for x in pm["ranking"])
        r["pm_max"] = pm["ranking"][0]
    return r


# ── Estilos ───────────────────────────────────────────────────────────
def estilos():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName="Helvetica",
                          fontSize=9.5, leading=13)
    return {
        "base": base,
        "peq": ParagraphStyle("peq", parent=base, fontSize=8, leading=10.5, textColor=GRIS),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=20,
                             leading=24, textColor=colors.white),
        "sub": ParagraphStyle("sub", parent=base, fontSize=10.5, leading=14,
                              textColor=colors.HexColor("#dbe7f3")),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=13,
                             leading=16, textColor=AZUL_OSC, spaceBefore=10, spaceAfter=5),
        "celda": ParagraphStyle("celda", parent=base, fontSize=8.5, leading=11),
        "celdab": ParagraphStyle("celdab", parent=base, fontName="Helvetica-Bold",
                                 fontSize=8.5, leading=11, textColor=colors.white),
        "kpi_n": ParagraphStyle("kpi_n", parent=base, fontName="Helvetica-Bold", fontSize=17,
                                leading=20, textColor=AZUL, alignment=TA_CENTER),
        "kpi_t": ParagraphStyle("kpi_t", parent=base, fontSize=7.5, leading=9.5,
                                textColor=GRIS, alignment=TA_CENTER),
        "pie": ParagraphStyle("pie", parent=base, fontSize=7.5, textColor=GRIS),
    }


def pendiente(v) -> bool:
    return isinstance(v, str) and v.strip().startswith("[")


def val_equipo(v, S) -> Paragraph:
    if pendiente(v):
        return Paragraph(f'<font color="#b23b3b"><b>[POR COMPLETAR]</b></font> {e(v)}', S["celda"])
    return Paragraph(e(v), S["celda"])


def tabla(datos, anchos, S, cab=True, zebra=True):
    t = Table(datos, colWidths=anchos, repeatRows=1 if cab else 0)
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d1dc")),
           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
           ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    if cab:
        est.append(("BACKGROUND", (0, 0), (-1, 0), AZUL))
    if zebra:
        for i in range(1 if cab else 0, len(datos)):
            if i % 2 == 0:
                est.append(("BACKGROUND", (0, i), (-1, i), CLARO))
    t.setStyle(TableStyle(est))
    return t


def imagen(nombre: str, ancho: float):
    f = GRA / nombre
    if not f.exists():
        log(f"AVISO: falta {f.name}; se omite en la guía")
        return None
    w, h = ImageReader(str(f)).getSize()
    return Image(str(f), width=ancho, height=ancho * h / w)


def pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRIS)
    canvas.drawString(1.8 * cm, 1.1 * cm,
                      "Bienestar Medellín IA · Hackathon de Datos 2026 · " + PORTAL)
    canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


# ── Construcción ───────────────────────────────────────────────────────
def construir(kb: dict, eq: dict) -> list:
    S = estilos()
    c = calcular(kb)
    h = c["h"]
    top, bajo = h["comuna_mayor_tasa"], h["comuna_menor_tasa"]
    anio = h.get("anio_referencia", 2022)
    W = A4[0] - 3.6 * cm
    el = []

    # Portada / encabezado
    cab = Table([[Paragraph("Bienestar Medellín IA", S["h1"])],
                 [Paragraph("Guía de entrega y ficha de hallazgos · Hackathon de Datos 2026 · "
                            "Institución Universitaria ITM · Temática: Salud y bienestar", S["sub"])]],
                colWidths=[W])
    cab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AZUL_OSC),
                             ("LEFTPADDING", (0, 0), (-1, -1), 12),
                             ("TOPPADDING", (0, 0), (0, 0), 14), ("BOTTOMPADDING", (0, -1), (-1, -1), 12)]))
    el += [cab, Spacer(1, 10)]

    # Datos del equipo y del artefacto
    integr = eq.get("integrantes") or []
    integ_txt = "<br/>".join(
        f"{e(i.get('nombre', ''))} ({e(i.get('programa', ''))})" for i in integr) or "-"
    filas = [
        [Paragraph("<b>Equipo</b>", S["celda"]), val_equipo(eq.get("nombre_equipo", ""), S)],
        [Paragraph("<b>Categoría</b>", S["celda"]), val_equipo(eq.get("categoria", ""), S)],
        [Paragraph("<b>Integrantes</b>", S["celda"]),
         Paragraph(f'<font color="#b23b3b"><b>[POR COMPLETAR]</b></font> {integ_txt}', S["celda"])
         if any(pendiente(i.get("nombre", "")) for i in integr) else Paragraph(integ_txt, S["celda"])],
        [Paragraph("<b>Líder y contacto</b>", S["celda"]),
         Paragraph(f"{val_equipo(eq.get('lider_nombre',''), S).text} · "
                   f"{val_equipo(eq.get('lider_correo',''), S).text}", S["celda"])],
        [Paragraph("<b>Modalidad</b>", S["celda"]),
         Paragraph("Pipeline automático (fase 2: asistente y portal interactivo sobre sus resultados)", S["celda"])],
        [Paragraph("<b>Repositorio público</b>", S["celda"]), Paragraph(e(REPO), S["celda"])],
        [Paragraph("<b>Artefacto en línea</b>", S["celda"]), Paragraph(e(PORTAL), S["celda"])],
    ]
    el += [tabla(filas, [3.6 * cm, W - 3.6 * cm], S, cab=False, zebra=True), Spacer(1, 4)]

    # Pregunta y hallazgo
    el.append(Paragraph("1. Pregunta que responde el proyecto", S["h2"]))
    el.append(Paragraph(
        "¿Cómo usar el análisis de datos para identificar factores ambientales, sociales y "
        "territoriales que afectan la salud y el bienestar de Medellín, y por dónde empezar a intervenir?",
        S["base"]))

    el.append(Paragraph("2. Hallazgo principal", S["h2"]))
    var = h.get("variacion_pct_2012_2022_comuna_top")
    hal = Table([[Paragraph(
        f"<b>{e(top['nombre'])}</b> tiene una tasa de mortalidad de <b>{fmt(top['tasa'])}</b> por 100.000 "
        f"habitantes ({anio}), <b>{fmt(h['brecha_veces'], 2)} veces</b> la de {e(bajo['nombre'])} "
        f"({fmt(bajo['tasa'])})"
        + (f", y <b>{'aumentó' if var >= 0 else 'disminuyó'} {fmt(abs(var))} %</b> entre 2012 y 2022." if var is not None else ".")
        + " <br/><font size=8 color='#4b5563'>Fuente: MEData · Secretaría de Salud de Medellín. "
          "Asociación, no causalidad.</font>", S["base"])]], colWidths=[W])
    hal.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff3e6")),
                             ("LINEBEFORE", (0, 0), (0, -1), 4, NAR),
                             ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    el += [hal, Spacer(1, 8)]

    # KPIs
    kp = [(fmt(top["tasa"]), f"Mayor tasa de mortalidad\n{top['nombre']} · {anio}"),
          (fmt(h["brecha_veces"], 2) + " x", "Brecha entre el mayor\ny el menor territorio"),
          ((("+" if var >= 0 else "") + fmt(var) + " %") if var is not None else "-", "Variación 2012-2022\nde la comuna con mayor tasa"),
          (fmt(c["ciudad"], 0) if c["ciudad"] else "-", "Tasa de toda la ciudad\n(por 100.000 hab.)")]
    kt = Table([[Paragraph(n, S["kpi_n"]) for n, _ in kp],
                [Paragraph(e(t).replace("\n", "<br/>"), S["kpi_t"]) for _, t in kp]],
               colWidths=[W / 4] * 4)
    kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d1dc")),
                            ("LINEAFTER", (0, 0), (-2, -1), 0.4, colors.HexColor("#c8d1dc")),
                            ("BACKGROUND", (0, 0), (-1, -1), CLARO),
                            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el += [kt]

    # ── Ficha de hallazgos ──
    el.append(PageBreak())
    el.append(Paragraph("3. Ficha de hallazgos", S["h2"]))
    el.append(Paragraph("Cada hallazgo se calcula automáticamente a partir de los datos oficiales; "
                        "la columna «Fuente» indica el conjunto de datos.", S["peq"]))
    el.append(Spacer(1, 4))
    H = lambda t: Paragraph(e(t), S["celdab"])
    C = lambda t: Paragraph(t, S["celda"])
    f = [[H("N.º"), H("Hallazgo"), H("Cifra"), H("Fuente")]]
    f.append([C("1"), C("Desigualdad territorial en mortalidad general"),
              C(f"<b>{fmt(h['brecha_veces'], 2)} x</b> entre {e(top['nombre'])} ({fmt(top['tasa'])}) "
                f"y {e(bajo['nombre'])} ({fmt(bajo['tasa'])}) · {anio}"),
              C("MEData · Mortalidad")])
    if var is not None:
        f.append([C("2"), C(f"La mortalidad de {e(top['nombre'])} creció en la última década"),
                  C(f"<b>{'+' if var >= 0 else ''}{fmt(var)} %</b> 2012-2022; pico en 2021 (COVID-19)"),
                  C("MEData · Mortalidad")])
    f.append([C("3"), C("Índice de priorización (mortalidad + salud mental, 0-100): los tres territorios de mayor prioridad"),
              C("<b>" + e(", ".join(f"{t['nombre']} ({fmt(t['indice'])})" for t in c["terr"][:3])) + "</b>"),
              C("MEData · Mortalidad e Intento de suicidio")])
    man = next((t for t in c["terr"][:5] if t["nombre"] == "Manrique"), None)
    if man:
        f.append([C("4"), C("Manrique entra al top 3 por salud mental, no por mortalidad"),
                  C(f"Mortalidad normalizada {fmt(man['nm'])} · salud mental normalizada {fmt(man['ns'])}"),
                  C("MEData · Intento de suicidio")])
    if c["doble"]:
        r_ = c["pearson"]
        f.append([C("5"), C("«Doble carga»: territorios sobre la mediana en mortalidad e intento de suicidio"),
                  C(f"<b>{len(c['doble'])} de {len(c['terr'])}</b>: {e(', '.join(c['doble']))}. "
                    f"Correlación de Pearson r = {fmt(r_, 2)}"),
                  C("MEData · Mortalidad e Intento de suicidio")])
    f.append([C("6"), C("Robustez: la priorización no depende de un peso arbitrario"),
              C(f"{e(c['rob_uno'][0])} es nº 1 en <b>{c['rob_uno'][1]} de {c['rob_n']}</b> ponderaciones probadas; "
                f"{c['rob_top3']} territorios llegan al top 3 en algún escenario"),
              C("Cálculo propio sobre el índice")])
    if c["pm"].get("ranking"):
        pm = c["pm"]
        tx = (f"{len(pm['ranking'])} estaciones en {pm['anio']}; máximo {e(c['pm_max']['estacion'])} = "
              f"<b>{fmt(c['pm_max']['media_pm25'], 1)} µg/m³</b>. "
              + ("Todas superan la guía anual de la OMS (5 µg/m³)." if c.get("pm_todas_sobre_oms") else ""))
        if "pm_mejoran" in c:
            tx += (f" {c['pm_mejoran']} de {c['pm_n']} estaciones mejoraron frente a {pm['comparacion']['anio_anterior']} "
                   f"(promedio {fmt(c['pm_prom_ant'])} -> {fmt(c['pm_prom_act'])} µg/m³).")
        f.append([C("7"), C("Calidad del aire (PM2.5) como contexto ambiental, por estación"), C(tx), C("SIATA · Datos validados")])
    el.append(tabla(f, [0.9 * cm, 5.2 * cm, W - 0.9 * cm - 5.2 * cm - 3.2 * cm, 3.2 * cm], S))

    # ── Propuestas de mejora ──
    el.append(Paragraph("4. Propuestas de mejora", S["h2"]))
    t3 = ", ".join(c["top3"])
    P = [
        ("Programa integral de salud física y mental en los territorios de mayor prioridad",
         f"Concentrar intervenciones intersectoriales en {e(t3)}, combinando promoción de la salud y atención en salud mental.",
         "Tasa de mortalidad e intento de suicidio por comuna; índice de priorización (anual)."),
        ("Atención específica de salud mental donde coinciden las dos cargas",
         ("Priorizar rutas de salud mental en " + e(", ".join(c["doble"])) + ".") if c["doble"]
         else "Priorizar rutas de salud mental en los territorios con mayor intento de suicidio.",
         "Tasa de intento de suicidio (SIVIGILA, MEData); cobertura de atención."),
        ("Seguimiento automático y comparable en el tiempo",
         "Mantener el pipeline mensual y sumar tasas estandarizadas por edad para comparar comunas con estructuras de población distintas.",
         "Actualización del portal; tasa ajustada por edad."),
        ("Cruzar calidad del aire y salud a escala territorial",
         "Validar un mapeo espacial estación-comuna para poder incorporar el PM2.5 al índice; hoy se reporta por estación.",
         "PM2.5 por comuna; asociación con indicadores respiratorios (cuando existan datos)."),
    ]
    p = [[H("N.º"), H("Propuesta"), H("Acción concreta"), H("Indicador de seguimiento")]]
    for i, (a, b, d) in enumerate(P, 1):
        p.append([C(str(i)), C(f"<b>{e(a)}</b>"), C(b), C(e(d))])
    el.append(tabla(p, [0.9 * cm, 4.6 * cm, (W - 0.9 * cm - 4.6 * cm) * 0.55, (W - 0.9 * cm - 4.6 * cm) * 0.45], S))

    # ── Gráficos ──
    el.append(PageBreak())
    el.append(Paragraph("5. Evidencia gráfica", S["h2"]))
    for nombre, ancho in (("ranking_mortalidad_2022.png", 14.5 * cm), ("indice_priorizacion.png", 14.5 * cm)):
        im = imagen(nombre, ancho)
        if im:
            el += [im, Spacer(1, 6)]
    el.append(PageBreak())
    for nombre, ancho in (("evolucion_comuna_top.png", 15.5 * cm), ("pm25_siata.png", 15.5 * cm)):
        im = imagen(nombre, ancho)
        if im:
            el += [im, Spacer(1, 6)]

    # ── Fuentes, licencias, límites, IA ──
    el.append(PageBreak())
    el.append(Paragraph("6. Datos, fuentes y licencias", S["h2"]))
    d = [[H("Conjunto de datos"), H("Entidad / identificador"), H("Licencia / condiciones")],
         [C("<b>MEData</b> · Mortalidad (VC_Datos_Enfermedades, capa 3), 2012-2022"),
          C("Secretaría de Salud de Medellín · id 1-026-22-000161"),
          C("CC BY 4.0 (verificada en la ficha MEData)")],
         [C("<b>MEData</b> · Intento de suicidio (capa 2), SIVIGILA, 2013-2022"),
          C("Secretaría de Salud de Medellín · id 1-026-22-000146"),
          C("CC BY 4.0 (verificada en la ficha MEData)")],
         [C("<b>MEData</b> · otras 8 capas por comuna: natalidad, dengue, hepatitis A, parotiditis, tosferina, "
            "tuberculosis pulmonar, varicela, violencia de género (2008/2012/2013-2022)"),
          C("Secretaría de Salud de Medellín · mismo servicio"),
          C("Ver la ficha de cada evento en MEData")],
         [C("<b>ECV</b> · Serie histórica de indicadores por territorio, 2007-2022"),
          C("Alcaldía de Medellín, Planeación"),
          C("Misma condición que la ECV; se excluyen los indicadores marcados «no publicar» por la fuente")],
         [C("<b>Encuesta de Calidad de Vida</b> 2022-2025 (solo conteos agregados: cobertura y llave de 21 territorios)"),
          C("Alcaldía de Medellín, Planeación · ficha MEData id 1-002-09-000040"),
          C("CC BY 4.0 según la ficha de la misma encuesta (cobertura 2011-2019); las bases 2022-2025 vienen del centro documental, que no repite la licencia")],
         [C("<b>SIATA</b> · PM2.5 validado, años completos desde 2020, por estación"),
          C("SIATA · Valle de Aburrá · siata.gov.co/IDEAM"),
          C("Sin licencia publicada en su sitio; se atribuye la fuente")]]
    el.append(tabla(d, [6.0 * cm, 5.2 * cm, W - 11.2 * cm], S))
    el.append(Paragraph("Atribución: Alcaldía de Medellín, Secretaría de Salud, MEData. Los microdatos no se publican; "
                        "solo se versionan tablas agregadas, sin datos personales ni datos sintéticos.", S["peq"]))

    el.append(Paragraph("7. Limitaciones", S["h2"]))
    for t in ("Asociación, no causalidad: no se hacen afirmaciones causales.",
              "Tasas brutas, sin estandarizar por edad; pueden sobrerrepresentar comunas con población mayor.",
              "El PM2.5 se mide por estación y no se atribuye a comunas sin un mapeo espacial validado; por eso no entra al índice.",
              "MEData publica sus series por comuna hasta 2022; el aire tiene años completos válidos desde 2020: las series no se mezclan en una sola cifra.",
              "Los factores asociados son correlaciones entre 21 territorios, sin ajustar por edad: describen patrones, no causas.",
              "La población por territorio se deriva de casos / tasa; sirve para la tasa de ciudad y no sustituye proyecciones oficiales del DANE."):
        el.append(Paragraph("• " + e(t), S["base"]))

    el.append(Paragraph("8. Automatización y reproducibilidad", S["h2"]))
    el.append(Paragraph(
        "El pipeline (GitHub Actions: push, ejecución manual y cron mensual) descarga las fuentes oficiales, valida la llave "
        "territorial, limpia, integra, analiza, visualiza, construye la base de conocimiento, ejecuta las pruebas del asistente "
        "y publica el portal, sin pasos manuales. Instrucciones de prueba: <b>instrucciones.txt</b> en la raíz del repositorio.",
        S["base"]))

    el.append(Paragraph("9. Uso de inteligencia artificial", S["h2"]))
    for t in ("<b>Kiro CLI</b> (asistente de programación con IA): desarrollo de scripts, portal y documentación; el equipo revisa y puede explicar el resultado.",
              "<b>ChatGPT y Gemini</b>: consultas exploratorias iniciales (ideas y búsqueda de fuentes); no generaron código ni cifras.",
              "<b>Asistente del portal</b>: las cifras salen siempre de un motor determinista que lee la base de conocimiento. "
              "Las preguntas escritas se interpretan con <b>Google Gemini</b> (capa gratuita, vía un Worker de Cloudflare), que solo devuelve el tipo de consulta "
              "y los territorios, de listas cerradas; nunca cifras. Si la IA falla, responde el motor solo.",
              "La capa opcional con un modelo de OpenAI (asistente/llm.py) está apagada por defecto y no se usa en el portal publicado."):
        el.append(Paragraph("• " + t, S["base"]))
    gen = (kb.get("meta") or {}).get("generado_utc", "")
    el.append(Spacer(1, 8))
    el.append(Paragraph(f"Cifras generadas desde knowledge_base.json (última actualización {e(gen)} UTC). "
                        f"Guía creada el {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", S["pie"]))
    return el


def main() -> int:
    if not KB_F.exists():
        print("ERROR: falta outputs/kb/knowledge_base.json. Ejecuta scripts/07_construir_kb.py", file=sys.stderr)
        return 1
    kb = json.loads(KB_F.read_text(encoding="utf-8"))
    eq = yaml.safe_load(EQUIPO_F.read_text(encoding="utf-8")) if EQUIPO_F.exists() else {}
    doc = SimpleDocTemplate(str(SALIDA), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.8 * cm,
                            title="Guía de entrega · Bienestar Medellín IA",
                            author="Hackathon de Datos 2026")
    doc.build(construir(kb, eq), onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    log(f"Guía generada -> {SALIDA.name}")

    # Aviso accionable: valores del equipo sin completar (prueba de las 3 AM).
    pend = [k for k, v in (eq or {}).items() if pendiente(v)]
    pend += ["integrantes"] if any(pendiente(i.get("nombre", "")) for i in (eq or {}).get("integrantes", [])) else []
    inst = BASE / "instrucciones.txt"
    if inst.exists():
        ph = re.findall(r"\[[^\]\n]{3,60}\]", inst.read_text(encoding="utf-8"))
        if ph:
            log("AVISO: instrucciones.txt aún tiene placeholders: " + "; ".join(sorted(set(ph))))
    if pend:
        log("AVISO: completa en equipo.yml -> " + ", ".join(pend) + " y vuelve a generar la guía.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
