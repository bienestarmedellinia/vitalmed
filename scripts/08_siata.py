#!/usr/bin/env python3
"""
08_siata.py — Procesa PM2.5 de SIATA por estación (dimensión ambiental).

Lee los ZIP mensuales descargados en data/raw/siata/, extrae los archivos
PM2.5_<ESTACION><AÑO>-<MES>.xls (OLE binario, columna 6 = Concentracion),
y agrega por estación y año.

ADVERTENCIA METODOLÓGICA: SIATA mide por ESTACIÓN, no por comuna. No se
atribuye PM2.5 a comunas sin un mapeo espacial validado. Se reporta por estación.

Criterio de validez SIATA: se exige >=75% de datos válidos en el periodo para
considerar representativo el promedio (informe de calidad del aire SIATA).

Salida: outputs/tablas/siata_pm25_estacion.csv y siata_cobertura.json
Se ejecuta en GitHub Actions (xlrd no apto para la Raspberry Pi en lote).
"""
from __future__ import annotations
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw" / "siata"
OUT = BASE / "outputs" / "tablas"

COL_ESTACION = 0
COL_CONCENTRACION = 6
HORAS_MES_MIN = 0.75  # 75% de validez
# Rango físicamente plausible de PM2.5 horario (µg/m³). Los archivos usan
# centinelas como 99999 para dato faltante (verificado: ENV-HOSP, mayo 2021);
# se descartan para no inflar las medias.
PM25_MIN, PM25_MAX = 0.0, 1000.0

# Horas teóricas por mes (aprox) para el criterio de validez.
HORAS_POR_MES = {1: 744, 2: 672, 3: 744, 4: 720, 5: 744, 6: 720,
                 7: 744, 8: 744, 9: 720, 10: 744, 11: 720, 12: 744}


def log(msg: str) -> None:
    print(f"[siata] {msg}", flush=True)


def leer_xls_pm25(data: bytes) -> tuple[str, list[float]]:
    """Devuelve (estacion, lista de concentraciones válidas) de un .xls."""
    import xlrd
    wb = xlrd.open_workbook(file_contents=data)
    sh = wb.sheet_by_index(0)
    estacion = str(sh.cell_value(1, COL_ESTACION)) if sh.nrows > 1 else "?"
    valores = []
    for r in range(1, sh.nrows):
        v = sh.cell_value(r, COL_CONCENTRACION)
        if isinstance(v, (int, float)) and v == v and PM25_MIN <= v <= PM25_MAX:
            valores.append(float(v))  # excluye NaN, negativos y centinelas (99999)
    return estacion, valores


def mes_de_nombre(nombre: str) -> int | None:
    m = re.search(r"(\d{4})-(\d{2})\.xls$", nombre)
    return int(m.group(2)) if m else None


def anio_de_nombre(nombre: str) -> int | None:
    m = re.search(r"(\d{4})-(\d{2})\.xls$", nombre)
    return int(m.group(1)) if m else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not RAW.exists():
        log("No hay data/raw/siata/. Ejecuta 01_descargar.py primero.")
        return 0

    registros = []  # (estacion, anio, mes, media, n, validez)
    zips = sorted(RAW.glob("*.zip"))
    log(f"{len(zips)} ZIP SIATA a procesar")
    for z in zips:
        try:
            with zipfile.ZipFile(z) as zf:
                for nombre in zf.namelist():
                    base = Path(nombre).name
                    if not base.startswith("PM2.5_") or not base.endswith(".xls"):
                        continue
                    anio, mes = anio_de_nombre(base), mes_de_nombre(base)
                    if anio is None:
                        continue
                    estacion, vals = leer_xls_pm25(zf.read(nombre))
                    if not vals:
                        continue
                    horas = HORAS_POR_MES.get(mes, 720)
                    validez = len(vals) / horas
                    registros.append({
                        "estacion": estacion, "anio": anio, "mes": mes,
                        "media_pm25": round(sum(vals) / len(vals), 2),
                        "n_horas": len(vals), "validez": round(validez, 3),
                    })
        except Exception as e:  # noqa: BLE001
            log(f"error en {z.name}: {e}")

    if not registros:
        log("No se encontraron archivos PM2.5 en los ZIP.")
        return 0

    df = pd.DataFrame(registros)
    # Agregación anual por estación, solo meses con >=75% de validez.
    validos = df[df["validez"] >= HORAS_MES_MIN]
    anual = (validos.groupby(["estacion", "anio"])
                     .agg(media_pm25=("media_pm25", "mean"),
                          meses_validos=("mes", "nunique"))
                     .reset_index())
    anual["media_pm25"] = anual["media_pm25"].round(2)
    anual = anual.sort_values(["anio", "media_pm25"], ascending=[True, False])

    salida = OUT / "siata_pm25_estacion.csv"
    anual.to_csv(salida, index=False, encoding="utf-8")

    # Cobertura: meses con archivo PM2.5 publicado por año (define si un año
    # está completo; ver 07_construir_kb.py).
    cobertura = {int(a): int(n) for a, n in df.groupby("anio")["mes"].nunique().items()}
    (OUT / "siata_cobertura.json").write_text(
        json.dumps({"meses_por_anio": cobertura}, indent=2), encoding="utf-8")
    log(f"Cobertura (meses por año): {cobertura}")
    log(f"PM2.5 por estación/año -> {salida} ({len(anual)} filas)")
    log(f"Estaciones: {sorted(anual['estacion'].unique().tolist())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
