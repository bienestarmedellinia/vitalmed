#!/usr/bin/env python3
"""
06_visualizar.py — Visualizaciones (headless, para GitHub Actions).

Genera PNG sin necesidad de display (backend Agg):
  outputs/graficos/ranking_mortalidad_2022.png   ranking por comuna
  outputs/graficos/evolucion_comuna_top.png       serie temporal 2012-2022
  outputs/graficos/pipeline.png                    diagrama del funcionamiento

No requiere interacción. Datos agregados por comuna (sin PII).
"""
from __future__ import annotations
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


def log(msg: str) -> None:
    print(f"[visualizar] {msg}", flush=True)


def grafico_ranking() -> None:
    df = pd.read_csv(TAB / "analisis_mortalidad_comuna.csv")
    df = df.sort_values("tasa", ascending=True)
    fig, ax = plt.subplots(figsize=(10, 7))
    colores = [NAR if i == len(df) - 1 else AZUL for i in range(len(df))]
    ax.barh(df["nombre"].astype(str), df["tasa"], color=colores)
    ax.set_xlabel("Tasa de mortalidad (defunciones por 100.000 hab.)")
    ax.set_title("Mortalidad por comuna · Medellín 2022\nFuente: MEData — Secretaría de Salud")
    for y, (t, c) in enumerate(zip(df["tasa"], df["casos"])):
        ax.text(t + 3, y, f"{t:.0f}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GRA / "ranking_mortalidad_2022.png", dpi=130)
    plt.close(fig)
    log("ranking_mortalidad_2022.png")


def grafico_evolucion() -> None:
    mort = RAW / "medata" / "mortalidad.csv"
    df = pd.read_csv(mort)
    df["comuna"] = pd.to_numeric(df["comuna"], errors="coerce")
    ref = pd.read_csv(TAB / "analisis_mortalidad_comuna.csv").iloc[0]
    top = int(ref["comuna"])
    fila = df[df["comuna"] == top].iloc[0]
    anios = list(range(2012, 2023))
    tasas = [fila.get(f"tasa_{a}") for a in anios]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(anios, tasas, marker="o", color=NAR, linewidth=2)
    ax.set_title(f"Evolución de la tasa de mortalidad · {ref['nombre']} (comuna {top})")
    ax.set_xlabel("Año")
    ax.set_ylabel("Tasa por 100.000 hab.")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(GRA / "evolucion_comuna_top.png", dpi=130)
    plt.close(fig)
    log("evolucion_comuna_top.png")


def grafico_pipeline() -> None:
    """Diagrama del funcionamiento del pipeline (lo pidió el equipo)."""
    pasos = [
        ("Fuentes oficiales\nECV · SIATA · MEData", AZUL),
        ("01 Descargar\n(desde la fuente)", AZUL),
        ("03 Validar\nllave territorial", NAR),
        ("02 Limpiar\nhomologar comuna", AZUL),
        ("04 Integrar\npor territorio", AZUL),
        ("05 Analizar\nhallazgo + cifra", NAR),
        ("06 Visualizar\nPNG", AZUL),
    ]
    fig, ax = plt.subplots(figsize=(13, 3.2))
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
                fontsize=8.5, color=color, weight="bold")
        centros.append(x + 1.5)
        x += 2.0
    for i in range(len(pasos) - 1):
        ar = FancyArrowPatch((centros[i], 1.0), (centros[i] + 0.5, 1.0),
                             arrowstyle="-|>", mutation_scale=14, color=GRIS)
        ax.add_patch(ar)
    ax.text(len(pasos), 0.15,
            "Todo el cómputo corre en GitHub Actions (no en la Raspberry Pi)",
            ha="center", fontsize=9, style="italic", color=GRIS)
    fig.tight_layout()
    fig.savefig(GRA / "pipeline.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    log("pipeline.png")


def main() -> int:
    GRA.mkdir(parents=True, exist_ok=True)
    grafico_ranking()
    grafico_evolucion()
    grafico_pipeline()
    log("Visualizaciones generadas en outputs/graficos/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
