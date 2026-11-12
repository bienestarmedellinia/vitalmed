#!/usr/bin/env python3
"""
16_pitch_slides.py — Genera presentacion_pitch.pdf (diapositivas de apoyo).

Material de apoyo del pitch de 5 minutos del Hackathon de Datos ITM 2026
(equipos finalistas). Formato: PDF apaisado 16:9, una diapositiva por tramo del
guion oficial (problema/usuario 45 s · datos/método 75 s · demo 120 s · aporte/
límites 60 s), más portada y cierre. Abre en cualquier navegador/visor, sin
PowerPoint. Todas las cifras son reales (del proyecto / KB).

Salida: presentacion_pitch.pdf (raíz del repo)
Requiere reportlab.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "presentacion_pitch.pdf"

# Lienzo 16:9 (33.87 x 19.05 cm ~ ancho carta apaisado a 16:9)
W, H = 33.87 * cm, 19.05 * cm

AZUL = colors.HexColor("#1f4e79")
AZUL_OSC = colors.HexColor("#0f2a44")
NAR = colors.HexColor("#d9731a")
GRIS = colors.HexColor("#4b5563")
CLARO = colors.HexColor("#eef2f7")
BLANCO = colors.white


def e(x) -> str:
    t = str(x)
    for a, b in (("≥", ">="), ("→", "->"), ("≈", "~"), ("’", "'")):
        t = t.replace(a, b)
    return escape(t)


h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=30,
                    textColor=AZUL_OSC, leading=34)
tiempo = ParagraphStyle("tiempo", fontName="Helvetica-Bold", fontSize=15,
                        textColor=NAR, leading=18)
vineta = ParagraphStyle("vineta", fontName="Helvetica", fontSize=18,
                        textColor=colors.HexColor("#1a1a1a"), leading=26,
                        spaceAfter=6, alignment=TA_LEFT)
dato = ParagraphStyle("dato", fontName="Helvetica-Bold", fontSize=18,
                      textColor=AZUL, leading=26, spaceAfter=6)


def fondo(c, titulo_tramo, numero):
    """Dibuja la plantilla base de cada slide de contenido."""
    # barra lateral
    c.setFillColor(AZUL)
    c.rect(0, 0, 0.5 * cm, H, stroke=0, fill=1)
    # pie
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 9)
    c.drawString(1.2 * cm, 0.7 * cm,
                 "MCC GLOBAL SOLUTIONS · Bienestar Medellín IA — Vitalmed · Hackathon de Datos ITM 2026")
    c.drawRightString(W - 1.2 * cm, 0.7 * cm, str(numero))


def vinetas(c, items, x=1.6 * cm, top=H - 4.6 * cm, w=None):
    """Renderiza una lista de Paragraphs apilados."""
    if w is None:
        w = W - 3.2 * cm
    y = top
    for style, text in items:
        p = Paragraph(text, style)
        pw, ph = p.wrap(w, 6 * cm)
        p.drawOn(c, x, y - ph)
        y -= ph + 0.25 * cm


def slide_titulo_tramo(c, titulo, seg):
    c.setFillColor(AZUL_OSC)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(1.6 * cm, H - 2.7 * cm, titulo)
    if seg:
        c.setFillColor(NAR)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(1.6 * cm, H - 3.5 * cm, seg)
    # línea
    c.setStrokeColor(CLARO)
    c.setLineWidth(2)
    c.line(1.6 * cm, H - 3.9 * cm, W - 1.6 * cm, H - 3.9 * cm)


def main() -> int:
    c = canvas.Canvas(str(SALIDA), pagesize=(W, H))
    c.setTitle("Pitch — MCC GLOBAL SOLUTIONS — Bienestar Medellín IA Vitalmed")
    c.setAuthor("MCC GLOBAL SOLUTIONS")

    # ── Slide 1 · Portada ──────────────────────────────────────────────
    c.setFillColor(AZUL_OSC)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(NAR)
    c.rect(0, H - 0.6 * cm, W, 0.6 * cm, stroke=0, fill=1)
    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 40)
    c.drawString(2.2 * cm, H - 6.5 * cm, "Bienestar Medellín IA")
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(colors.HexColor("#8fc1ff"))
    c.drawString(2.2 * cm, H - 8.2 * cm, "Vitalmed · Observatorio del bienestar")
    c.setFillColor(BLANCO)
    c.setFont("Helvetica", 17)
    c.drawString(2.2 * cm, H - 10.2 * cm,
                 "El bienestar de Medellín es desigual y multidimensional.")
    c.drawString(2.2 * cm, H - 10.9 * cm,
                 "6 fuentes oficiales, 21 territorios, 13 dimensiones — en un solo observatorio.")
    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#c7d6e8"))
    c.drawString(2.2 * cm, H - 13.0 * cm,
                 "MCC GLOBAL SOLUTIONS · Categoría Interna · Pipelines automáticos + Visualización")
    c.drawString(2.2 * cm, H - 13.8 * cm,
                 "Walter Andrés Tabares (líder) · Jorge Alexander Marín · ITM, Ing. de Sistemas")
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(2.2 * cm, 1.4 * cm, "bienestarmedellinia.github.io/vitalmed")
    c.showPage()

    # ── Slide 2 · Problema y usuario · 45 s ─────────────────────────────
    fondo(c, "problema", 2)
    slide_titulo_tramo(c, "1 · Problema y usuario", "45 segundos")
    vinetas(c, [
        (vineta, "El bienestar en Medellín es <b>profundamente desigual</b> entre sus "
                 "<b>21 territorios</b>: salud, empleo, seguridad alimentaria, cultura y aire."),
        (vineta, "La información <b>existe en fuentes oficiales</b>, pero está dispersa y es "
                 "difícil de cruzar para decidir <b>dónde intervenir primero</b>."),
        (dato, "Usuario: planeación y secretarías de la Alcaldía (Salud, Planeación, "
               "Bienestar) · academia y público general."),
    ])
    c.showPage()

    # ── Slide 3 · Datos y método · 75 s ─────────────────────────────────
    fondo(c, "datos", 3)
    slide_titulo_tramo(c, "2 · Datos y método", "75 segundos")
    vinetas(c, [
        (dato, "MEData (obligatorio): VC_Datos_Enfermedades · 10 capas por comuna, 2008–2022."),
        (vineta, "<b>+5 fuentes:</b> ECV (Alcaldía), SIATA (PM2.5), DANE EEVV, SIVIGILA y RIPS."),
        (vineta, "Pipeline en <b>GitHub Actions</b>: descarga → valida → limpia → integra por "
                 "territorio (16 comunas + 5 corregimientos), homologando la llave de la ECV "
                 "(p_006 / P_007 / A.7)."),
        (dato, "8 correlaciones significativas (Pearson + Spearman, 95%) · la más fuerte: "
               "mortalidad–hepatitis A, r=0,69."),
    ])
    c.showPage()

    # ── Slide 4 · Demostración · 120 s ──────────────────────────────────
    fondo(c, "demo", 4)
    slide_titulo_tramo(c, "3 · Demostración del artefacto", "120 segundos")
    vinetas(c, [
        (vineta, "<b>1.</b> Abrir el portal → hero con la pregunta y el hallazgo."),
        (vineta, "<b>2.</b> Entrar a una categoría → análisis técnico con semáforo por tendencia."),
        (vineta, "<b>3.</b> Mapa interactivo → colorear los 21 territorios por indicador y año "
                 "(mortalidad 2022: La Candelaria en rojo) + red de correlaciones."),
        (vineta, "<b>4.</b> Descargar el CSV de la vista."),
        (vineta, "<b>5.</b> Automatización: Actions → pipeline «pipeline-principal» con "
                 "ejecuciones correctas y la carpeta outputs/."),
    ])
    c.showPage()

    # ── Slide 5 · El hallazgo (dato grande) ─────────────────────────────
    fondo(c, "hallazgo", 5)
    slide_titulo_tramo(c, "El dato que el jurado debe recordar", "")
    c.setFillColor(NAR)
    c.setFont("Helvetica-Bold", 58)
    c.drawString(1.8 * cm, H - 9.2 * cm, "1.325,6")
    c.setFillColor(AZUL_OSC)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(1.8 * cm, H - 10.4 * cm, "muertes por 100.000 hab. — La Candelaria, 2022 (1.074 casos)")
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 17)
    c.drawString(1.8 * cm, H - 12.0 * cm,
                 "4,58× la tasa del corregimiento de Santa Elena (289,5) · +44,6% entre 2012 y 2022.")
    c.setFont("Helvetica-Oblique", 15)
    c.drawString(1.8 * cm, H - 13.2 * cm,
                 "Es un ejemplo: la brecha se repite en las 13 dimensiones del observatorio.")
    c.showPage()

    # ── Slide 6 · Aporte a MEData y limitaciones · 60 s ─────────────────
    fondo(c, "aporte", 6)
    slide_titulo_tramo(c, "4 · Aporte a MEData y limitaciones", "60 segundos")
    vinetas(c, [
        (dato, "Aporte: que MEData publique las capas por comuna desde 2023, con desglose por "
               "edad y sexo → tasas estandarizadas y brechas ajustadas."),
        (vineta, "<b>Límites (declarados en el portal y el KB):</b>"),
        (vineta, "• Asociación, no causalidad · tasas brutas sin estandarizar por edad."),
        (vineta, "• MEData no publica por comuna tras 2022 · niveles mixtos (DANE/SIVIGILA/RIPS "
                 "municipales, PM2.5 por estación) · efecto COVID 2020–2021."),
    ])
    c.showPage()

    # ── Slide 7 · Cierre ────────────────────────────────────────────────
    c.setFillColor(AZUL_OSC)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(NAR)
    c.rect(0, 0, W, 0.6 * cm, stroke=0, fill=1)
    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(2.2 * cm, H - 6.5 * cm, "Datos dispersos → decisión con evidencia")
    c.setFont("Helvetica", 18)
    c.setFillColor(colors.HexColor("#c7d6e8"))
    c.drawString(2.2 * cm, H - 8.6 * cm,
                 "Un observatorio auditable, reproducible y automático para priorizar el bienestar de Medellín.")
    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2.2 * cm, H - 11.4 * cm, "Portal:  bienestarmedellinia.github.io/vitalmed")
    c.drawString(2.2 * cm, H - 12.3 * cm, "Repo:    github.com/bienestarmedellinia/vitalmed")
    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#c7d6e8"))
    c.drawString(2.2 * cm, 1.4 * cm,
                 "Presentan: Walter Tabares (mensaje central, 1 y 4) · Jorge Marín (2 y 3, demo en vivo). ¡Gracias!")
    c.showPage()

    c.save()
    print(f"[slides] generado {SALIDA.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
