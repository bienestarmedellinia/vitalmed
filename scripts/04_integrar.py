#!/usr/bin/env python3
"""
04_integrar.py — Integración territorial (solo agregados, sin PII).

Combina las bases ECV homologadas en una tabla por comuna/corregimiento y
año (conteo de personas/hogares encuestados). Esta tabla AGREGADA es la
única que se publica en el repositorio: no contiene datos personales.

Produce:
  outputs/tablas/resumen_territorial.csv   (publicable)

Se ejecuta en GitHub Actions.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "data" / "processed"
OUT = BASE / "outputs" / "tablas"


def log(msg: str) -> None:
    print(f"[integrar] {msg}", flush=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    parquets = sorted(PROC.glob("ecv_*_homologado.parquet"))
    if not parquets:
        log("No hay bases homologadas en data/processed/. Ejecuta 02_limpiar.py.")
        return 1

    resumenes = []
    for p in parquets:
        df = pd.read_parquet(p, columns=["anio", "territorio_cod",
                                         "territorio_nombre", "tipo_territorio"])
        agg = (df.groupby(["anio", "territorio_cod", "territorio_nombre",
                           "tipo_territorio"], dropna=False)
                 .size().reset_index(name="registros_encuestados"))
        resumenes.append(agg)
        log(f"{p.name}: {len(agg)} territorios agregados")

    resumen = pd.concat(resumenes, ignore_index=True)
    resumen = resumen.sort_values(["anio", "territorio_cod"]).reset_index(drop=True)

    salida = OUT / "resumen_territorial.csv"
    resumen.to_csv(salida, index=False, encoding="utf-8")
    log(f"Tabla agregada publicable -> {salida} ({len(resumen)} filas)")

    # Chequeo rápido de integración: todos los años deben cubrir 21 territorios.
    cobertura = resumen.groupby("anio")["territorio_cod"].nunique()
    log(f"Cobertura territorial por año:\n{cobertura.to_string()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
