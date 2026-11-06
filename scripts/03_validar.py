#!/usr/bin/env python3
"""
03_validar.py — Validación de consistencia de las bases ECV.

Se ejecuta en GitHub Actions (NO en la Raspberry Pi: las bases completas
saturan su RAM). Verifica que la llave territorial de integración sea
consistente entre años y cubra las 16 comunas + 5 corregimientos.

La variable territorial se codifica así en todas las bases validadas:
    comunas        -> 1..16
    corregimientos -> 50, 60, 70, 80, 90   (21 territorios en total)

Sale con código != 0 si alguna base no cumple, de modo que el pipeline
falla visiblemente y el jurado ve la validación como parte del artefacto.
"""
from __future__ import annotations
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
SOURCES = Path(__file__).resolve().parent / "sources.yml"

# Territorios esperados: 16 comunas + 5 corregimientos.
COMUNAS = set(range(1, 17))
CORREGIMIENTOS = {50, 60, 70, 80, 90}
ESPERADOS = COMUNAS | CORREGIMIENTOS


def log(msg: str) -> None:
    print(f"[validar] {msg}", flush=True)


def leer_columna_territorial(anio: str, var: str, formato: str, sep: str) -> pd.Series:
    """Lee SOLO la columna territorial (bajo consumo de memoria)."""
    d = RAW / f"ecv_{anio}"
    if formato == "csv":
        archivo = d / "base.csv"
        s = pd.read_csv(archivo, sep=sep, usecols=[var], low_memory=False,
                        encoding="utf-8", encoding_errors="replace")[var]
    else:  # xlsx -> openpyxl read-only, una sola columna
        import openpyxl
        archivo = d / "base.xlsx"
        wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        header = list(next(rows))
        idx = header.index(var)
        vals = [r[idx] for r in rows]
        wb.close()
        s = pd.Series(vals, name=var)
    return pd.to_numeric(s, errors="coerce").dropna().astype(int)


def validar_anio(anio: str, var: str, formato: str, sep: str) -> list[str]:
    errores: list[str] = []
    try:
        serie = leer_columna_territorial(anio, var, formato, sep)
    except FileNotFoundError:
        log(f"ECV {anio}: base no descargada, se omite")
        return errores
    presentes = set(serie.unique().tolist())
    n_filas = len(serie)
    log(f"ECV {anio} ({var}): filas={n_filas} territorios={sorted(presentes)}")

    faltan = ESPERADOS - presentes
    sobran = presentes - ESPERADOS
    if faltan:
        errores.append(f"ECV {anio}: faltan territorios esperados: {sorted(faltan)}")
    if sobran:
        errores.append(f"ECV {anio}: valores territoriales inesperados: {sorted(sobran)}")
    if n_filas == 0:
        errores.append(f"ECV {anio}: columna territorial vacía")
    return errores


def _validar(t) -> list[str]:
    return validar_anio(*t)


def main() -> int:
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    ecv = cfg["ecv"]
    archivos = ecv["archivos"]
    terr = ecv["variable_territorial"]

    trabajos = [(a, terr[a], m.get("formato", "xlsx"), m.get("csv_sep", ";"))
                for a, m in archivos.items() if terr.get(a)]
    todos_errores: list[str] = []
    # Un proceso por año (lectura de XLSX es CPU-bound).
    with ProcessPoolExecutor(max_workers=min(4, len(trabajos) or 1)) as ex:
        for errores in ex.map(_validar, trabajos):
            todos_errores += errores

    print("\n" + "=" * 60)
    if todos_errores:
        log("VALIDACIÓN FALLIDA:")
        for e in todos_errores:
            print(f"   ✗ {e}")
        return 1
    log("VALIDACIÓN OK: llave territorial consistente en todas las bases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
