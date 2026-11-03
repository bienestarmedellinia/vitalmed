#!/usr/bin/env python3
"""
05_analizar.py — Análisis y hallazgo cuantificado por comuna.

Cruza, a nivel de comuna/corregimiento:
  - MEData · Secretaría de Salud: mortalidad y natalidad (casos y tasa por año)
  - ECV: cobertura muestral social por territorio (de 04_integrar)

Produce un hallazgo principal con cifra y una tabla analítica publicable:
  outputs/tablas/analisis_mortalidad_comuna.csv
  outputs/tablas/hallazgo.json          (cifra principal, para la ficha)

Se ejecuta en GitHub Actions. Datos agregados por comuna, sin PII.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
OUT = BASE / "outputs" / "tablas"

ANIO_REF = 2022          # último año disponible en MEData salud
ANIO_INI = 2012          # inicio de la serie

# Territorios válidos: 16 comunas + 5 corregimientos. Excluye códigos
# residuales de la fuente como 99 = "Sin información de comuna".
TERRITORIOS_VALIDOS = set(range(1, 17)) | {50, 60, 70, 80, 90}


def log(msg: str) -> None:
    print(f"[analizar] {msg}", flush=True)


def cargar_salud(nombre: str, prefijo_casos: str) -> pd.DataFrame:
    """Carga una capa de salud MEData en formato largo (comuna, anio, casos, tasa)."""
    f = RAW / "medata" / f"{nombre}.csv"
    df = pd.read_csv(f)
    # 'comuna' viene como '01'..'16'; filtramos solo comunas numéricas.
    df["comuna"] = pd.to_numeric(df["comuna"], errors="coerce")
    df = df.dropna(subset=["comuna"])
    df["comuna"] = df["comuna"].astype(int)
    # Mantener solo los 21 territorios oficiales (excluye 99 "Sin información").
    df = df[df["comuna"].isin(TERRITORIOS_VALIDOS)].copy()

    registros = []
    for anio in range(ANIO_INI, ANIO_REF + 1):
        col_casos = f"{prefijo_casos}_{anio}"
        col_tasa = f"tasa_{anio}"
        if col_casos not in df.columns or col_tasa not in df.columns:
            continue
        tmp = df[["comuna", "nombre", col_casos, col_tasa]].copy()
        tmp.columns = ["comuna", "nombre", "casos", "tasa"]
        tmp["anio"] = anio
        registros.append(tmp)
    largo = pd.concat(registros, ignore_index=True)
    largo["evento"] = nombre
    return largo


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    mort = cargar_salud("mortalidad", "casos")
    log(f"mortalidad: {mort['comuna'].nunique()} comunas, "
        f"años {mort['anio'].min()}-{mort['anio'].max()}")

    # ── Hallazgo 1: ranking de mortalidad por comuna en el año de referencia ──
    ref = (mort[mort["anio"] == ANIO_REF]
           .sort_values("tasa", ascending=False)
           .reset_index(drop=True))
    top = ref.iloc[0]
    bottom = ref.iloc[-1]
    brecha = top["tasa"] / bottom["tasa"] if bottom["tasa"] else float("nan")

    # ── Hallazgo 2: evolución 2012 -> 2022 de la comuna más afectada ──
    serie_top = mort[mort["comuna"] == int(top["comuna"])].sort_values("anio")
    t_ini = serie_top[serie_top["anio"] == ANIO_INI]["tasa"]
    t_fin = serie_top[serie_top["anio"] == ANIO_REF]["tasa"]
    var_pct = None
    if len(t_ini) and len(t_fin) and float(t_ini.iloc[0]):
        var_pct = (float(t_fin.iloc[0]) / float(t_ini.iloc[0]) - 1) * 100

    # Tabla analítica publicable
    ref.to_csv(OUT / "analisis_mortalidad_comuna.csv", index=False, encoding="utf-8")

    hallazgo = {
        "evento": "mortalidad general",
        "fuente": "MEData - Secretaría de Salud de Medellín (VC_Datos_Enfermedades)",
        "anio_referencia": ANIO_REF,
        "unidad_tasa": "defunciones por 100.000 habitantes",
        "comuna_mayor_tasa": {
            "comuna": int(top["comuna"]),
            "nombre": str(top["nombre"]),
            "tasa": round(float(top["tasa"]), 2),
            "casos": int(top["casos"]),
        },
        "comuna_menor_tasa": {
            "comuna": int(bottom["comuna"]),
            "nombre": str(bottom["nombre"]),
            "tasa": round(float(bottom["tasa"]), 2),
            "casos": int(bottom["casos"]),
        },
        "brecha_veces": round(float(brecha), 2),
        "variacion_pct_2012_2022_comuna_top": (
            round(var_pct, 1) if var_pct is not None else None),
        "serie_temporal_comuna_top": {
            "anios": [int(a) for a in serie_top["anio"].tolist()],
            "tasas": [round(float(t), 2) for t in serie_top["tasa"].tolist()],
        },
    }
    (OUT / "hallazgo.json").write_text(
        json.dumps(hallazgo, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Mensaje de hallazgo (el que va a la ficha / pitch) ──
    print("\n" + "=" * 64)
    log("HALLAZGO PRINCIPAL")
    print(f"  En {ANIO_REF}, la comuna con mayor tasa de mortalidad fue "
          f"{hallazgo['comuna_mayor_tasa']['nombre']} "
          f"(comuna {hallazgo['comuna_mayor_tasa']['comuna']}) con "
          f"{hallazgo['comuna_mayor_tasa']['tasa']} "
          f"defunciones por 100.000 hab.")
    print(f"  Es {hallazgo['brecha_veces']}x la de la comuna con menor tasa "
          f"({hallazgo['comuna_menor_tasa']['nombre']}: "
          f"{hallazgo['comuna_menor_tasa']['tasa']}).")
    if var_pct is not None:
        print(f"  Entre {ANIO_INI} y {ANIO_REF} su tasa varió {var_pct:+.1f}%.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
