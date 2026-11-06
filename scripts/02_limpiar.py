#!/usr/bin/env python3
"""
02_limpiar.py — Limpieza y homologación de las bases ECV.

Para cada año: lee la base, renombra la variable territorial heterogénea
(p_006 / P_007 / A.7) a una columna común 'territorio_cod', añade los
nombres oficiales de comunas/corregimientos y escribe un parquet liviano
en data/processed/.

Se ejecuta en GitHub Actions. Lee las bases por bloques para no agotar RAM.
NO se cruzan microdatos individuales entre fuentes (regla de privacidad):
la integración posterior se hace solo con agregados.
"""
from __future__ import annotations
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


import pandas as pd
import yaml

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
PROC = BASE / "data" / "processed"
SOURCES = Path(__file__).resolve().parent / "sources.yml"

# Nombres oficiales de las 16 comunas y 5 corregimientos de Medellín.
NOMBRES_TERRITORIO = {
    1: "Popular", 2: "Santa Cruz", 3: "Manrique", 4: "Aranjuez",
    5: "Castilla", 6: "Doce de Octubre", 7: "Robledo", 8: "Villa Hermosa",
    9: "Buenos Aires", 10: "La Candelaria", 11: "Laureles-Estadio",
    12: "La América", 13: "San Javier", 14: "El Poblado", 15: "Guayabal",
    16: "Belén",
    50: "Palmitas", 60: "San Cristóbal", 70: "Altavista",
    80: "San Antonio de Prado", 90: "Santa Elena",
}


def log(msg: str) -> None:
    print(f"[limpiar] {msg}", flush=True)


def cargar_base(anio: str, var: str, formato: str, sep: str) -> pd.DataFrame:
    d = RAW / f"ecv_{anio}"
    if formato == "csv":
        df = pd.read_csv(d / "base.csv", sep=sep, low_memory=False,
                         encoding="utf-8", encoding_errors="replace")
    else:
        df = pd.read_excel(d / "base.xlsx", sheet_name=0)
    if var not in df.columns:
        raise KeyError(f"ECV {anio}: no se encontró la variable territorial '{var}'")
    df = df.rename(columns={var: "territorio_cod"})
    df["territorio_cod"] = pd.to_numeric(df["territorio_cod"], errors="coerce").astype("Int64")
    df["territorio_nombre"] = df["territorio_cod"].map(NOMBRES_TERRITORIO)
    df["anio"] = int(anio)
    df["tipo_territorio"] = df["territorio_cod"].apply(
        lambda c: "corregimiento" if pd.notna(c) and int(c) >= 50 else "comuna"
    )
    return df


def _procesar_anio(t) -> str:
    anio, var, formato, sep = t
    try:
        df = cargar_base(anio, var, formato, sep)
    except FileNotFoundError:
        return f"ECV {anio}: base no descargada, se omite"
    salida = PROC / f"ecv_{anio}_homologado.parquet"
    df.to_parquet(salida, index=False)
    return f"ECV {anio}: {len(df)} filas -> {salida.name}"


def main() -> int:
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    ecv = cfg["ecv"]
    terr = ecv["variable_territorial"]
    PROC.mkdir(parents=True, exist_ok=True)

    trabajos = [(a, terr[a], m.get("formato", "xlsx"), m.get("csv_sep", ";"))
                for a, m in ecv["archivos"].items() if terr.get(a)]
    # Un proceso por año: leer XLSX grandes es CPU-bound (openpyxl).
    with ProcessPoolExecutor(max_workers=min(4, len(trabajos) or 1)) as ex:
        for msg in ex.map(_procesar_anio, trabajos):
            log(msg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
