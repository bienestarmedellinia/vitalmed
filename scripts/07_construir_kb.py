#!/usr/bin/env python3
"""
07_construir_kb.py — Construye el knowledge base del asistente (fase 2).

Consolida los resultados del pipeline (tablas agregadas + hallazgo) en un
único JSON estructurado que el asistente consulta. El asistente NO vuelve a
leer los microdatos: solo este KB con cifras ya calculadas y verificadas.

Salida: outputs/kb/knowledge_base.json

Se ejecuta en GitHub Actions como paso 7, tras el análisis.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
TAB = BASE / "outputs" / "tablas"
KB = BASE / "outputs" / "kb"


def log(msg: str) -> None:
    print(f"[kb] {msg}", flush=True)


def main() -> int:
    KB.mkdir(parents=True, exist_ok=True)
    kb: dict = {"meta": {}, "indicadores": {}, "territorios": {}, "fuentes": {}}

    # ── Metadatos y fuentes (trazabilidad) ──
    kb["meta"] = {
        "proyecto": "Medellín, Bienestar Basado en Datos",
        "descripcion": ("Knowledge base del asistente de inteligencia territorial. "
                        "Todas las cifras provienen del pipeline reproducible; "
                        "el asistente no inventa datos."),
        "territorios_oficiales": 21,
    }
    kb["fuentes"] = {
        "ecv": {"nombre": "Encuesta de Calidad de Vida de Medellín",
                "entidad": "Alcaldía de Medellín", "anios": [2022, 2023, 2024, 2025]},
        "medata_salud": {"nombre": "VC_Datos_Enfermedades",
                         "entidad": "Secretaría de Salud de Medellín",
                         "nivel": "comuna", "serie": "2012-2022"},
        "siata": {"nombre": "Datos validados de calidad del aire",
                  "entidad": "SIATA - Valle de Aburrá", "variable": "PM2.5"},
    }

    # ── Hallazgo principal ──
    hallazgo_f = TAB / "hallazgo.json"
    if hallazgo_f.exists():
        hallazgo = json.loads(hallazgo_f.read_text(encoding="utf-8"))
        kb["indicadores"]["hallazgo_mortalidad"] = hallazgo
        log("hallazgo.json incorporado")
        # Acceso directo al índice multivariable (si el análisis lo generó).
        if "indice_priorizacion" in hallazgo:
            kb["indicadores"]["indice_priorizacion"] = hallazgo["indice_priorizacion"]
            log(f"índice de priorización: "
                f"{len(hallazgo['indice_priorizacion']['ranking'])} comunas")

    # ── Ranking de mortalidad por comuna (año de referencia) ──
    mort_f = TAB / "analisis_mortalidad_comuna.csv"
    if mort_f.exists():
        df = pd.read_csv(mort_f)
        kb["indicadores"]["mortalidad_2022"] = {
            "unidad": "defunciones por 100.000 habitantes",
            "anio": 2022,
            "ranking": [
                {"comuna": int(r.comuna), "nombre": str(r.nombre),
                 "tasa": round(float(r.tasa), 2), "casos": int(r.casos)}
                for r in df.itertuples()
            ],
        }
        log(f"ranking mortalidad: {len(df)} territorios")

    # ── Cobertura muestral ECV por territorio/año ──
    res_f = TAB / "resumen_territorial.csv"
    if res_f.exists():
        df = pd.read_csv(res_f)
        por_terr: dict = {}
        for r in df.itertuples():
            nombre = str(r.territorio_nombre)
            por_terr.setdefault(nombre, {})[int(r.anio)] = int(r.registros_encuestados)
        kb["territorios"] = {
            "cobertura_ecv": por_terr,
            "anios_disponibles": sorted(df["anio"].unique().tolist()),
        }
        log(f"cobertura ECV: {len(por_terr)} territorios")

    # ── PM2.5 por estación (SIATA, dimensión ambiental) ──
    siata_f = TAB / "siata_pm25_estacion.csv"
    if siata_f.exists():
        df = pd.read_csv(siata_f)
        anio_ref = int(df["anio"].max())
        ref = (df[df["anio"] == anio_ref]
               .sort_values("media_pm25", ascending=False))
        kb["indicadores"]["pm25_siata"] = {
            "unidad": "µg/m³ (media anual)",
            "anio": anio_ref,
            "nivel": "estación de monitoreo (NO comuna)",
            "advertencia": ("SIATA mide por estación, no por comuna. No se atribuye "
                            "PM2.5 a comunas sin un mapeo espacial validado."),
            "ranking": [
                {"estacion": str(r.estacion), "media_pm25": round(float(r.media_pm25), 2),
                 "meses_validos": int(r.meses_validos)}
                for r in ref.itertuples()
            ],
        }
        log(f"PM2.5 SIATA: {len(ref)} estaciones (año {anio_ref})")

    salida = KB / "knowledge_base.json"
    contenido = json.dumps(kb, indent=2, ensure_ascii=False)
    salida.write_text(contenido, encoding="utf-8")
    log(f"Knowledge base -> {salida}")

    # Copia para el asistente web estático (GitHub Pages sirve desde docs/).
    docs = BASE / "docs"
    if docs.exists():
        (docs / "knowledge_base.json").write_text(contenido, encoding="utf-8")
        log("Knowledge base copiado a docs/ (asistente web)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
