#!/usr/bin/env python3
"""
06_visualizar.py — Visualizaciones (headless, para GitHub Actions).

Genera PNG sin necesidad de display (backend Agg):
  outputs/graficos/ranking_mortalidad_2022.png     ranking por comuna (anotado)
  outputs/graficos/evolucion_comuna_top.png         serie temporal 2012-2022 (anotada)
  outputs/graficos/indice_priorizacion.png          índice multivariable (barras apiladas)
  outputs/graficos/pm25_siata.png                   PM2.5 por estación 2024 vs 2025 (ambiental)
  outputs/graficos/pipeline.png                      diagrama del funcionamiento (8 pasos)

No requiere interacción. Datos agregados por comuna/estación (sin PII).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless: sin ventana ni display
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
TAB = BASE / "outputs" / "tablas"
GRA = BASE / "outputs" / "graficos"

AZUL = "#1f4e79"
NAR = "#d9731a"
GRIS = "#8a8a8a"
VERDE = "#2e7d32"
ROJO = "#b23b3b"


def log(msg: str) -> None:
    print(f"[visualizar] {msg}", flush=True)


def grafico_ranking() -> None:
    """Ranking de mortalidad por comuna, anotando el hallazgo (brecha 4,58×)."""
    df = pd.read_csv(TAB / "analisis_mortalidad_comuna.csv")
    df = df.sort_values("tasa", ascending=True).reset_index(drop=True)
    top = df.iloc[-1]       # mayor tasa (La Candelaria)
    bottom = df.iloc[0]     # menor tasa (Santa Elena)
    brecha = top["tasa"] / bottom["tasa"] if bottom["tasa"] else float("nan")

    fig, ax = plt.subplots(figsize=(10, 7))
    colores = [NAR if i == len(df) - 1 else AZUL for i in range(len(df))]
    ax.barh(df["nombre"].astype(str), df["tasa"], color=colores)
    ax.set_xlabel("Tasa de mortalidad (defunciones por 100.000 hab.)")
    ax.set_title("Mortalidad por comuna · Medellín 2022\nFuente: MEData — Secretaría de Salud")
    for y, t in enumerate(df["tasa"]):
        ax.text(t + 3, y, f"{t:.0f}", va="center", fontsize=8)

    # Anotación del hallazgo principal sobre la barra top.
    y_top = len(df) - 1
    ax.annotate(
        f"La Candelaria: {top['tasa']:.0f}\n{brecha:.2f}× la tasa de\n{bottom['nombre']} ({bottom['tasa']:.0f})",
        xy=(top["tasa"], y_top - 0.4),
        xytext=(top["tasa"] * 0.62, 6.5),
        ha="left",
        fontsize=9, color=NAR, weight="bold",
        bbox=dict(boxstyle="round,pad=0.4", fc="#fff3e6", ec=NAR, lw=1),
        arrowprops=dict(arrowstyle="->", color=NAR, lw=1.3),
    )
    fig.tight_layout()
    fig.savefig(GRA / "ranking_mortalidad_2022.png", dpi=130)
    plt.close(fig)
    log("ranking_mortalidad_2022.png")


def grafico_evolucion() -> None:
    """Serie temporal de La Candelaria, anotando pico 2021 (COVID) y Δ2012-2022."""
    hallazgo = json.loads((TAB / "hallazgo.json").read_text(encoding="utf-8"))
    ref = pd.read_csv(TAB / "analisis_mortalidad_comuna.csv").iloc[0]
    serie = hallazgo.get("serie_temporal_comuna_top", {})
    anios = serie.get("anios")
    tasas = serie.get("tasas")

    if not anios or not tasas:
        # Fallback: leer de los microdatos crudos si el hallazgo no trae la serie.
        df = pd.read_csv(RAW / "medata" / "mortalidad.csv")
        df["comuna"] = pd.to_numeric(df["comuna"], errors="coerce")
        top = int(ref["comuna"])
        fila = df[df["comuna"] == top].iloc[0]
        anios = list(range(2012, 2023))
        tasas = [fila.get(f"tasa_{a}") for a in anios]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(anios, tasas, marker="o", color=NAR, linewidth=2)
    ax.set_title(f"Evolución de la tasa de mortalidad · {ref['nombre']} (comuna {int(ref['comuna'])})")
    ax.set_xlabel("Año")
    ax.set_ylabel("Tasa por 100.000 hab.")
    ax.grid(alpha=0.3)

    # Anotar el pico máximo (2021 = COVID).
    i_max = max(range(len(tasas)), key=lambda i: tasas[i])
    ax.annotate(
        f"Pico {anios[i_max]}: {tasas[i_max]:.0f}\n(impacto COVID-19)",
        xy=(anios[i_max], tasas[i_max]),
        xytext=(anios[i_max] - 4.2, tasas[i_max] * 0.99),
        fontsize=9, color=ROJO, weight="bold",
        bbox=dict(boxstyle="round,pad=0.4", fc="#fdecec", ec=ROJO, lw=1),
        arrowprops=dict(arrowstyle="->", color=ROJO, lw=1.3),
    )

    # Anotar la variación 2012→2022.
    var = hallazgo.get("variacion_pct_2012_2022_comuna_top")
    if var is not None:
        ax.text(
            0.02, 0.95, f"+{var:.1f}% entre {anios[0]} y {anios[-1]}",
            transform=ax.transAxes, fontsize=10, color=AZUL, weight="bold",
            va="top", bbox=dict(boxstyle="round,pad=0.4", fc="#eaf1f8", ec=AZUL, lw=1),
        )
    fig.tight_layout()
    fig.savefig(GRA / "evolucion_comuna_top.png", dpi=130)
    plt.close(fig)
    log("evolucion_comuna_top.png")


def grafico_indice() -> None:
    """Índice multivariable: barras apiladas mortalidad vs salud mental.

    Hace visible el hallazgo clave: comunas que priorizan por salud mental
    (ej. Manrique) y no solo por mortalidad. Componentes normalizados 0-100.
    """
    df = pd.read_csv(TAB / "indice_priorizacion_comuna.csv")
    # Orden descendente por índice; mostrar de mayor (arriba) a menor.
    df = df.sort_values("indice", ascending=True).reset_index(drop=True)
    nombres = df["nombre"].astype(str)
    # Contribución de cada componente al índice (promedio => cada uno aporta /2).
    aporte_mort = df["n_mortalidad"] / 2.0
    aporte_sui = df["n_suicidio"] / 2.0

    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.barh(nombres, aporte_mort, color=AZUL, label="Mortalidad general")
    ax.barh(nombres, aporte_sui, left=aporte_mort, color=NAR,
            label="Salud mental (intento de suicidio)")
    ax.set_xlabel("Índice de priorización en salud (0–100)")
    ax.set_title("Índice multivariable de priorización en salud · Medellín 2022\n"
                 "Fuente: MEData — mortalidad general + intento de suicidio (normalizados 0–100)")
    for y, v in enumerate(df["indice"]):
        ax.text(v + 1, y, f"{v:.0f}", va="center", fontsize=8, color="#333")
    ax.legend(loc="lower right", fontsize=9, framealpha=0.95)

    # Resaltar un caso que entra por salud mental (Manrique, comuna 3).
    if (df["comuna"] == 3).any():
        y_man = int(df.index[df["comuna"] == 3][0])
        ax.annotate(
            "Manrique sube al top por\nsalud mental, no por mortalidad",
            xy=(df.loc[y_man, "indice"], y_man),
            xytext=(df.loc[y_man, "indice"] + 8, y_man - 2.4),
            fontsize=8.5, color=NAR, weight="bold",
            bbox=dict(boxstyle="round,pad=0.35", fc="#fff3e6", ec=NAR, lw=1),
            arrowprops=dict(arrowstyle="->", color=NAR, lw=1.2),
        )
    fig.tight_layout()
    fig.savefig(GRA / "indice_priorizacion.png", dpi=130)
    plt.close(fig)
    log("indice_priorizacion.png")


def grafico_pm25() -> None:
    """PM2.5 por estación SIATA, comparando 2024 vs 2025, con guía OMS."""
    df = pd.read_csv(TAB / "siata_pm25_estacion.csv")
    piv = df.pivot_table(index="estacion", columns="anio", values="media_pm25")
    anios = sorted(c for c in piv.columns)
    # Ordenar por el último año disponible (desc) para lectura clara.
    orden = piv.sort_values(anios[-1], ascending=True)
    estaciones = orden.index.astype(str)

    fig, ax = plt.subplots(figsize=(10, 9))
    y = range(len(estaciones))
    h = 0.4
    colores_anio = {anios[0]: GRIS, anios[-1]: AZUL}
    for k, a in enumerate(anios):
        offset = (k - (len(anios) - 1) / 2) * h
        ax.barh([i + offset for i in y], orden[a], height=h,
                color=colores_anio.get(a, AZUL), label=str(int(a)))
    ax.set_yticks(list(y))
    ax.set_yticklabels(estaciones, fontsize=8)
    ax.set_xlabel("PM2.5 media anual (µg/m³)")
    ax.set_title("Calidad del aire (PM2.5) por estación · Valle de Aburrá\nFuente: SIATA")

    # Guía anual OMS 2021: 5 µg/m³ (recomendación).
    oms = 5.0
    ax.axvline(oms, color=VERDE, linestyle="--", linewidth=1.5)
    ax.text(oms + 0.3, len(estaciones) - 0.5,
            "Guía OMS anual: 5 µg/m³", color=VERDE, fontsize=9, weight="bold",
            va="top")
    ax.legend(title="Año", loc="center right", fontsize=9)
    fig.text(0.5, 0.005,
             "SIATA mide por estación, no por comuna: contexto ambiental "
             "(no se atribuye a comunas).",
             ha="center", fontsize=8, style="italic", color=GRIS)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(GRA / "pm25_siata.png", dpi=130)
    plt.close(fig)
    log("pm25_siata.png")


def grafico_pipeline() -> None:
    """Diagrama del funcionamiento del pipeline: refleja los 8 pasos reales."""
    pasos = [
        ("Fuentes oficiales\nECV · SIATA · MEData", AZUL),
        ("01 Descargar\n(desde la fuente)", AZUL),
        ("03 Validar\nllave territorial", NAR),
        ("02 Limpiar\nhomologar comuna", AZUL),
        ("04 Integrar\npor territorio", AZUL),
        ("05 Analizar\nhallazgo + índice", NAR),
        ("06 Visualizar\ngráficos PNG", AZUL),
        ("08 SIATA\nPM2.5 ambiental", NAR),
        ("07 Construir KB\n+ probar asistente", AZUL),
    ]
    fig, ax = plt.subplots(figsize=(16, 3.4))
    ax.set_xlim(0, len(pasos) * 2)
    ax.set_ylim(0, 2)
    ax.axis("off")
    x = 0.4
    centros = []
    for texto, color in pasos:
        box = FancyBboxPatch((x, 0.5), 1.5, 1.0,
                             boxstyle="round,pad=0.05,rounding_size=0.1",
                             linewidth=1.5, edgecolor=color, facecolor="white")
        ax.add_patch(box)
        ax.text(x + 0.75, 1.0, texto, ha="center", va="center",
                fontsize=8, color=color, weight="bold")
        centros.append(x + 1.5)
        x += 2.0
    for i in range(len(pasos) - 1):
        ar = FancyArrowPatch((centros[i], 1.0), (centros[i] + 0.5, 1.0),
                             arrowstyle="-|>", mutation_scale=14, color=GRIS)
        ax.add_patch(ar)
    ax.text(len(pasos), 0.12,
            "Todo el cómputo corre en GitHub Actions (no en la Raspberry Pi) · "
            "salida: tablas + gráficos + knowledge base del asistente",
            ha="center", fontsize=9, style="italic", color=GRIS)
    fig.tight_layout()
    fig.savefig(GRA / "pipeline.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    log("pipeline.png")


def main() -> int:
    GRA.mkdir(parents=True, exist_ok=True)
    grafico_ranking()
    grafico_evolucion()
    grafico_indice()
    grafico_pm25()
    grafico_pipeline()
    log("Visualizaciones generadas en outputs/graficos/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
