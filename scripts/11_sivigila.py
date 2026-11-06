#!/usr/bin/env python3
"""
11_sivigila.py — Serie SEMANAL de eventos SIVIGILA para Medellín.

Consulta el dataset agregado y abierto del INS en datos.gov.co (API SoQL, sin
token) y construye la serie semanal de dos eventos en Medellín (5001):
  - 345 ESI-IRAG (vigilancia centinela)  → proxy respiratorio (cruce con PM2.5)
  - 356 Intento de suicidio              → salud mental

Salida: outputs/tablas/sivigila_semanal.csv (cod_eve,evento,anio,semana,casos)
        outputs/tablas/sivigila_cobertura.json

ADVERTENCIA METODOLÓGICA: nivel MUNICIPAL (no comuna). ESI-IRAG es vigilancia
CENTINELA (no toda la morbilidad respiratoria). 2020-2021 = COVID (confusor).
Las semanas sin casos NO aparecen en la fuente → se consideran 0 (se declara).
Asociación, no causalidad.

Liviano (solo consultas agregadas SoQL + stdlib). Corre en Actions.
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
TIMEOUT = 120


def log(msg: str) -> None:
    print(f"[sivigila] {msg}", flush=True)


def soql(endpoint: str, params: dict) -> list[dict]:
    url = f"{endpoint}?{urlencode(params)}"
    req = Request(url, headers=UA)
    with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (endpoint oficial fijo)
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    sv = cfg.get("sivigila")
    if not sv:
        log("No hay sección 'sivigila' en sources.yml")
        return 0

    endpoint = sv["endpoint"]
    obj = sv["municipio_objetivo"]
    eventos = sv["eventos"]
    codigos = list(eventos.keys())
    where = (f"cod_mun_o='{obj['cod_mun_o']}' AND cod_eve in("
             + ",".join(f"'{c}'" for c in codigos) + ")")

    try:
        filas_raw = soql(endpoint, {
            "$select": "cod_eve,ano,semana,sum(conteo::number) as casos",
            "$where": where,
            "$group": "cod_eve,ano,semana",
            "$order": "cod_eve,ano,semana",
            "$limit": "50000",
        })
    except Exception as e:  # noqa: BLE001
        log(f"error consultando SIVIGILA: {e}")
        return 0

    if not filas_raw:
        log("La consulta no devolvió filas.")
        return 0

    filas = []
    cobertura = {}  # cod_eve -> {anios:[...], semanas:n}
    for r in filas_raw:
        cod = r["cod_eve"]
        anio = int(r["ano"])
        sem = int(r["semana"])
        casos = int(float(r["casos"]))
        filas.append({"cod_eve": cod, "evento": eventos[cod]["nombre"],
                      "anio": anio, "semana": sem, "casos": casos})
        c = cobertura.setdefault(cod, {"anios": set(), "semanas": 0})
        c["anios"].add(anio)
        c["semanas"] += 1

    salida = OUT / "sivigila_semanal.csv"
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cod_eve", "evento", "anio", "semana", "casos"])
        w.writeheader()
        w.writerows(filas)

    cob_json = {
        "municipio": obj,
        "nivel": "municipio de ocurrencia (NO comuna)",
        "periodicidad": "semanal (semana epidemiológica)",
        "nota": ("ESI-IRAG es vigilancia CENTINELA (no toda la morbilidad). "
                 "Semanas sin casos no aparecen en la fuente = 0. "
                 "2020-2021: COVID como confusor."),
        "eventos": {c: {**eventos[c],
                        "anios": sorted(cobertura[c]["anios"]),
                        "semanas_con_casos": cobertura[c]["semanas"]}
                    for c in cobertura},
    }
    (OUT / "sivigila_cobertura.json").write_text(
        json.dumps(cob_json, indent=2, ensure_ascii=False), encoding="utf-8")
    for c in cobertura:
        aa = sorted(cobertura[c]["anios"])
        log(f"{c} {eventos[c]['nombre']}: {aa[0]}-{aa[-1]}, "
            f"{cobertura[c]['semanas']} semanas con casos")
    log(f"SIVIGILA semanal -> {salida} ({len(filas)} filas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
