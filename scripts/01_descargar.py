#!/usr/bin/env python3
"""
01_descargar.py — Descarga los datos desde las fuentes oficiales.

Lee scripts/sources.yml y descarga ECV (bases + diccionarios) y SIATA
(archivos mensuales de calidad del aire) a data/raw/.

Diseñado para ejecutarse en GitHub Actions, NO en la Raspberry Pi.
No modifica ni interpreta los datos; solo descarga y registra procedencia.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from pathlib import Path

import requests
import yaml

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
SOURCES = Path(__file__).resolve().parent / "sources.yml"

TIMEOUT = 120
RETRIES = 3
HEADERS = {"User-Agent": "MedellinBienestarDatos/1.0 (hackathon ITM 2026)"}


def log(msg: str) -> None:
    print(f"[descargar] {msg}", flush=True)


def descargar(url: str, destino: Path) -> dict:
    """Descarga una URL a destino con reintentos. Devuelve metadatos."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    ultimo_error = None
    for intento in range(1, RETRIES + 1):
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT, headers=HEADERS) as r:
                r.raise_for_status()
                h = hashlib.sha256()
                total = 0
                with open(destino, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        if chunk:
                            f.write(chunk)
                            h.update(chunk)
                            total += len(chunk)
            log(f"OK  {destino.name}  ({total/1e6:.1f} MB)")
            return {
                "url": url,
                "archivo": str(destino.relative_to(BASE)),
                "bytes": total,
                "sha256": h.hexdigest(),
            }
        except Exception as e:  # noqa: BLE001
            ultimo_error = e
            log(f"intento {intento}/{RETRIES} fallo para {url}: {e}")
            time.sleep(3 * intento)
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo_error}")


def descargar_arcgis(servicio: str, capa: int, destino: Path) -> dict:
    """Descarga todos los registros de una capa ArcGIS (paginado) y los
    guarda como CSV. El servicio requiere User-Agent de navegador."""
    import csv

    destino.parent.mkdir(parents=True, exist_ok=True)
    ua = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")}
    base_q = f"{servicio}/{capa}/query"
    offset, page, filas, campos = 0, 2000, [], None
    while True:
        params = {
            "where": "1=1", "outFields": "*", "returnGeometry": "false",
            "resultOffset": offset, "resultRecordCount": page, "f": "json",
        }
        r = requests.get(base_q, params=params, headers=ua, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        feats = data.get("features", [])
        if campos is None:
            campos = [f["name"] for f in data.get("fields", [])]
        for feat in feats:
            filas.append(feat.get("attributes", {}))
        if len(feats) < page or not data.get("exceededTransferLimit", False):
            if len(feats) < page:
                break
        offset += page
        if offset > 100000:  # guarda de seguridad
            break

    if not filas:
        raise RuntimeError(f"capa {capa}: sin registros")
    if campos is None:
        campos = list(filas[0].keys())

    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for row in filas:
            w.writerow({k: row.get(k) for k in campos})

    total = destino.stat().st_size
    h = hashlib.sha256(destino.read_bytes()).hexdigest()
    log(f"OK  {destino.name}  ({len(filas)} filas, {total/1e3:.0f} KB)")
    return {"url": f"{base_q}?where=1=1&outFields=*&f=json",
            "archivo": str(destino.relative_to(BASE)),
            "bytes": total, "sha256": h, "filas": len(filas)}


def main() -> int:
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    manifiesto = []

    # ── ECV ──────────────────────────────────────────────────
    ecv = cfg["ecv"]["archivos"]
    for anio, archivos in ecv.items():
        destino_dir = RAW / f"ecv_{anio}"
        for tipo, url in archivos.items():
            if tipo in ("formato", "csv_sep", "nota"):
                continue
            if not url:
                log(f"SKIP ECV {anio}/{tipo}: sin URL en sources.yml")
                continue
            ext = Path(url).suffix or ".bin"
            destino = destino_dir / f"{tipo}{ext}"
            manifiesto.append({"fuente": f"ecv_{anio}", "tipo": tipo,
                               **descargar(url, destino)})

    # ── SIATA ────────────────────────────────────────────────
    s = cfg["siata"]
    patron = s["patron_url"]
    for anio in s["anios"]:
        for mes in s["meses"]:
            url = patron.format(mes=mes, anio=anio)
            destino = RAW / "siata" / f"{mes}{anio}.zip"
            try:
                manifiesto.append({"fuente": "siata", "tipo": f"{mes}{anio}",
                                   **descargar(url, destino)})
            except RuntimeError as e:
                # Un mes puede no existir todavía; no es fatal.
                log(f"SIATA {mes}{anio} no disponible: {e}")

    # ── MEData: servicio ArcGIS de salud por comuna (obligatorio) ─
    md = cfg.get("medata", {})
    servicio = md.get("servicio_rest")
    if servicio:
        capas = md.get("capas", {})
        prioritarias = md.get("capas_prioritarias") or list(capas.keys())
        for capa_id in prioritarias:
            nombre = capas.get(capa_id, f"capa_{capa_id}")
            destino = RAW / "medata" / f"{nombre}.csv"
            try:
                meta = descargar_arcgis(servicio, int(capa_id), destino)
                manifiesto.append({"fuente": "medata", "tipo": nombre, **meta})
            except RuntimeError as e:
                log(f"MEData capa {capa_id} ({nombre}) fallo: {e}")
    else:
        log("SKIP MEData: definir 'servicio_rest' en sources.yml (requisito obligatorio)")

    # Registro de procedencia (trazabilidad para el jurado)
    reg = RAW / "_manifiesto_descarga.json"
    reg.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Manifiesto escrito: {reg} ({len(manifiesto)} archivos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
