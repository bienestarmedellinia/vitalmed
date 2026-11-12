#!/usr/bin/env python3
"""
15_resumen_pitch.py — Genera MCCGLOBALSOLUTIONS_resumen_pitch.pdf (1 página).

Entregable SOLO para equipos finalistas del Hackathon de Datos ITM 2026.
Sigue el "Formato de resumen del pitch" de la Guía de Entrega v2 del ITM:
  - Equipo y proyecto
  - Mensaje central (pregunta + hallazgo, 1-2 frases)
  - 1. Problema y usuario · 45 s
  - 2. Datos y método · 75 s
  - 3. Demostración del artefacto · 120 s
  - 4. Aporte a MEData y limitaciones · 60 s
  - Quién presenta cada parte
  - Recursos para la presentación

Máximo UNA página. Todas las cifras son reales (del proyecto / KB).
El nombre del archivo sigue la regla de la guía: NombreEquipo_resumen_pitch.pdf.

Salida: resumen_pitch.pdf (raíz del repo)
Requiere reportlab (ya está en requirements.txt del pipeline).
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (KeepInFrame, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "resumen_pitch.pdf"

AZUL = colors.HexColor("#1f4e79")
AZUL_OSC = colors.HexColor("#0f2a44")
NAR = colors.HexColor("#d9731a")
GRIS = colors.HexColor("#4b5563")
CLARO = colors.HexColor("#eef2f7")


def e(x) -> str:
    t = str(x)
    for a, b in (("≥", ">="), ("→", "->"), ("≈", "~"), ("’", "'"), ("·", "·")):
        t = t.replace(a, b)
    return escape(t)


# ── Estilos (compactos para que todo quepa en 1 página) ────────────────
titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=13,
                        textColor=AZUL_OSC, leading=15, spaceAfter=1)
sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8.5,
                     textColor=GRIS, leading=10, spaceAfter=3)
seccion = ParagraphStyle("seccion", fontName="Helvetica-Bold", fontSize=9.2,
                        textColor=colors.white, leading=11)
etq = ParagraphStyle("etq", fontName="Helvetica-Oblique", fontSize=7.3,
                    textColor=GRIS, leading=8.5, spaceAfter=1)
cuerpo = ParagraphStyle("cuerpo", fontName="Helvetica", fontSize=8.6,
                       textColor=colors.HexColor("#1a1a1a"), leading=10.6,
                       alignment=TA_LEFT, spaceAfter=1)
mensaje = ParagraphStyle("mensaje", fontName="Helvetica-Bold", fontSize=9.2,
                        textColor=AZUL_OSC, leading=11.5, spaceAfter=1)


def banda(texto: str):
    """Barra azul de título de sección."""
    p = Paragraph(e(texto), seccion)
    t = Table([[p]], colWidths=[17.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def bloque(nota: str, texto: str):
    """Etiqueta en gris (guía) + contenido."""
    items = []
    if nota:
        items.append(Paragraph(e(nota), etq))
    items.append(Paragraph(texto, cuerpo))
    return items


def main() -> int:
    doc = SimpleDocTemplate(
        str(SALIDA), pagesize=A4,
        topMargin=1.0 * cm, bottomMargin=0.9 * cm,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm,
        title="Resumen del pitch — MCC GLOBAL SOLUTIONS",
        author="MCC GLOBAL SOLUTIONS",
    )

    flow = []

    # Encabezado
    flow.append(Paragraph("Resumen del pitch — Hackathon de Datos ITM 2026", titulo))
    flow.append(Paragraph(
        "Solo equipos finalistas · Máximo una página · Modalidad: Pipelines automáticos + Visualización",
        sub))

    # Equipo y proyecto
    flow.append(banda("Equipo y proyecto"))
    flow.append(Spacer(1, 2))
    flow += bloque(
        "",
        "<b>MCC GLOBAL SOLUTIONS</b> · Proyecto <b>Bienestar Medellín IA — Vitalmed</b>. "
        "Observatorio web del bienestar multidimensional de Medellín, alimentado por un "
        "pipeline automático. Categoría Interna · Temática Salud y Bienestar.")
    flow.append(Spacer(1, 3))

    # Mensaje central
    flow.append(banda("Mensaje central"))
    flow.append(Spacer(1, 2))
    flow.append(Paragraph(
        "¿Dónde y en qué dimensión del bienestar están rezagados los 21 territorios de Medellín? "
        "Integramos 6 fuentes oficiales en un observatorio que lo responde al instante: el bienestar "
        "es desigual y multidimensional. El caso más fuerte —La Candelaria con "
        "<b>1.325,6 muertes por 100.000 hab. en 2022, 4,58× el corregimiento de Santa Elena</b>— "
        "es solo un ejemplo de brechas que se repiten en las 13 categorías.", mensaje))
    flow.append(Spacer(1, 3))

    # 1. Problema y usuario
    flow.append(banda("1 · Problema y usuario · 45 s"))
    flow.append(Spacer(1, 2))
    flow += bloque(
        "Qué problema de Medellín atienden y para quién.",
        "El bienestar en Medellín es profundamente desigual entre sus 21 territorios "
        "(salud, empleo, seguridad alimentaria, cultura, aire). La información existe en fuentes "
        "oficiales, pero está dispersa y es difícil de cruzar para decidir dónde intervenir. "
        "<b>Usuario:</b> equipos de planeación y secretarías de la Alcaldía (Salud, Planeación, "
        "Bienestar) y academia/público general.")
    flow.append(Spacer(1, 3))

    # 2. Datos y método
    flow.append(banda("2 · Datos y método · 75 s"))
    flow.append(Spacer(1, 2))
    flow += bloque(
        "Conjuntos de MEData y otras fuentes; cómo se limpiaron e integraron.",
        "<b>MEData</b> (obligatorio): VC_Datos_Enfermedades, 10 capas por comuna 2008–2022 "
        "(mortalidad, intento de suicidio, dengue, hepatitis A, tuberculosis, violencia de género…). "
        "<b>+5 fuentes:</b> ECV (Alcaldía), SIATA (PM2.5), DANE EEVV, SIVIGILA y RIPS. "
        "Un pipeline en GitHub Actions descarga, valida, limpia e integra por la llave territorial "
        "(16 comunas + 5 corregimientos), homologando la variable de la ECV que cambia de nombre cada "
        "año (p_006 / P_007 / A.7). Calcula un índice de priorización y correlaciones "
        "(Pearson + Spearman, 95%): <b>8 asociaciones significativas</b> (la más fuerte, "
        "mortalidad–hepatitis A, r=0,69).")
    flow.append(Spacer(1, 3))

    # 3. Demostración del artefacto
    flow.append(banda("3 · Demostración del artefacto · 120 s"))
    flow.append(Spacer(1, 2))
    flow += bloque(
        "Qué mostrarán, en qué orden y qué resultado verá el jurado.",
        "(1) Abrir el portal → hero con la pregunta y el hallazgo. "
        "(2) Entrar a una categoría → análisis técnico automático con semáforo por tendencia. "
        "(3) Mapa interactivo → colorear los 21 territorios por indicador y año (mortalidad 2022: "
        "La Candelaria en rojo) y la red de correlaciones. (4) Descargar el CSV de la vista. "
        "(5) Mostrar la automatización: pestaña Actions → historial del pipeline "
        "«pipeline-principal» con ejecuciones correctas y la carpeta outputs/.")
    flow.append(Spacer(1, 3))

    # 4. Aporte a MEData y limitaciones
    flow.append(banda("4 · Aporte a MEData y limitaciones · 60 s"))
    flow.append(Spacer(1, 2))
    flow += bloque(
        "Propuesta de apertura o mejora y lo que el resultado no permite afirmar.",
        "<b>Aporte:</b> solicitar que MEData publique las capas de enfermedades por comuna "
        "desde 2023 con desglose por edad y sexo, para habilitar tasas estandarizadas y análisis "
        "de brechas ajustadas. <b>Límites:</b> asociación, no causalidad; tasas brutas sin "
        "estandarizar por edad; MEData no publica por comuna tras 2022; niveles territoriales mixtos "
        "(DANE/SIVIGILA/RIPS son municipales, PM2.5 por estación); efecto COVID 2020–2021. "
        "Todo declarado en el portal y el KB.")
    flow.append(Spacer(1, 4))

    # Quién presenta + recursos (en dos columnas para ahorrar espacio)
    izq = [Paragraph("<b>Quién presenta cada parte</b>", cuerpo),
           Paragraph("Walter Tabares: mensaje central, 1 y 4 · "
                     "Jorge Marín: 2 y 3 (demostración en vivo).", cuerpo)]
    der = [Paragraph("<b>Recursos para la presentación</b>", cuerpo),
           Paragraph("Portátil propio, conexión a internet, portal "
                     "bienestarmedellinia.github.io/vitalmed y repositorio GitHub. "
                     "Respaldo si falla internet: capturas del portal y outputs/ ya versionados.",
                     cuerpo)]
    cols = Table([[izq, der]], colWidths=[8.4 * cm, 8.6 * cm])
    cols.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow.append(cols)

    # Forzar a 1 página: encoger si se pasa
    frame_w = A4[0] - 4.0 * cm
    frame_h = A4[1] - 1.9 * cm
    doc.build([KeepInFrame(frame_w, frame_h, flow, mode="shrink")])
    print(f"[pitch] generado {SALIDA.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
