#!/usr/bin/env python3
"""
12_rips.py — Morbilidad ANUAL por gran grupo CIE-10 (RIPS MinSalud), Medellín.

Consulta el dataset agregado y abierto de RIPS en datos.gov.co (API SoQL, sin
token) y construye la serie ANUAL de atenciones en Medellín (05001) para dos
grandes grupos CIE-10:
  - respiratorias (J00-J99)
  - mentales      (F00-F99)

Salida: outputs/tablas/rips_anual.csv (grupo,anio,atenciones)
        outputs/tablas/rips_cobertura.json

ADVERTENCIA METODOLÓGICA: granularidad ANUAL y MUNICIPAL (no comuna, no mes).
Es CONTEXTO de carga de morbilidad, NO serie para cruzar con picos de PM2.5.
Caída 2020-2021 por COVID/subregistro de consulta. Asociación, no causalidad.

Liviano (consultas agregadas SoQL + stdlib). Corre en Actions.
"""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "outputs" / "tablas"
SOURCES = Path(__file__).resolve().parent / "sources.yml"

UA = {"User-Agent": "MedellinBienestarDatos/1.0 (hackathon ITM 2026)"}
TIMEOUT = 180


def log(msg: str) -> None:
    print(f"[rips] {msg}", flush=True)


def soql(endpoint: str, params: dict) -> list[dict]:
    url = f"{endpoint}?{urlencode(params)}"
    req = Request(url, headers=UA)
    with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (endpoint oficial fijo)
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    rp = cfg.get("rips")
    if not rp:
        log("No hay sección 'rips' en sources.yml")
        return 0

    endpoint = rp["endpoint"]
    pref = rp["municipio_prefijo"]
    grupos = rp["grupos"]

    filas = []       # (grupo, anio, atenciones)
    cobertura = {}   # grupo -> años
    for clave, g in grupos.items():
        cie = g["prefijo_cie"]
        try:
            res = soql(endpoint, {
                "$select": "a_o,sum(`numeroatenciones`::number) as at",
                "$where": f"municipio like '{pref}%' AND starts_with(diagnostico,'{cie}')",
                "$group": "a_o",
                "$order": "a_o",
                "$limit": "100",
            })
        except Exception as e:  # noqa: BLE001
            log(f"grupo {clave}: error ({e}); se omite")
            continue
        anios = []
        for r in res:
            if not r.get("a_o") or r.get("at") is None:
                continue
            anio = int(r["a_o"])
            at = int(float(r["at"]))
            filas.append({"grupo": clave, "nombre": g["nombre"],
                          "anio": anio, "atenciones": at})
            anios.append(anio)
        cobertura[clave] = sorted(anios)
        if anios:
            log(f"{clave} ({g['nombre']}): {anios[0]}-{anios[-1]}, "
                f"{len(anios)} años")

    if not filas:
        log("No se agregó ninguna fila (¿fuente caída?).")
        return 0

    salida = OUT / "rips_anual.csv"
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["grupo", "nombre", "anio", "atenciones"])
        w.writeheader()
        w.writerows(filas)
    (OUT / "rips_cobertura.json").write_text(
        json.dumps({"municipio": rp.get("nombre_municipio", "Medellín"),
                    "nivel": "municipio (NO comuna)",
                    "periodicidad": "anual",
                    "nota": ("Contexto de carga de morbilidad (no serie para cruce "
                             "con PM2.5). Caída 2020-2021 por COVID/subregistro."),
                    "grupos": {k: grupos[k]["nombre"] for k in cobertura},
                    "anios": {k: cobertura[k] for k in cobertura}},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"RIPS anual -> {salida} ({len(filas)} filas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
