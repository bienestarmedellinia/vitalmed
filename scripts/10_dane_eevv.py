#!/usr/bin/env python3
"""
10_dane_eevv.py — Mortalidad DANE (Estadísticas Vitales) por mes y causa.

Descarga los ZIP de "Defunciones no fetales" del catálogo de microdatos del
DANE (uno por año, acceso anónimo), lee el CSV interno EN STREAMING (encoding
latin-1) y agrega la mortalidad de Medellín (05001, municipio de OCURRENCIA)
por AÑO × MES × gran grupo de causa CIE-10:

  - total            (todas las causas)
  - respiratorias    (C_BAS1 empieza por 'J', J00-J99)
  - circulatorias    (C_BAS1 empieza por 'I', contexto)

Salida: outputs/tablas/dane_mortalidad_mensual.csv (anio,mes,causa,defunciones)
        outputs/tablas/dane_cobertura.json (años/meses disponibles)

ADVERTENCIA METODOLÓGICA: granularidad MUNICIPAL (no comuna) y MENSUAL (no
diaria) → serie mensual Poisson, NO DLNM diario. Asociación, no causalidad.

Se ejecuta en GitHub Actions (NUNCA en la Raspberry Pi: cada CSV pesa ~69 MB;
se procesa en streaming para no cargar todo en memoria). KISS: solo stdlib.
"""
from __future__ import annotations
import csv
import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "outputs" / "tablas"
SOURCES = Path(__file__).resolve().parent / "sources.yml"

UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")}
TIMEOUT = 300


def log(msg: str) -> None:
    print(f"[dane_eevv] {msg}", flush=True)


def _http(url: str) -> bytes:
    req = Request(url, headers=UA)
    with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (URL fija oficial)
        return r.read()


def resolver_fileid(ficha: int) -> int | None:
    """Lee la página get-microdata del estudio y devuelve el fileid del archivo
    de defunciones NO fetales. El botón Descargar es un <input type=image> con
    title='BD-EEVV-...nofetal<AÑO>.zip' y onclick que llama a /download/<fileid>.
    El nombre del recurso varía por año (Defuncionesnofetales / nofetal), por eso
    se identifica por el title del botón, que sí es consistente."""
    url = f"https://microdatos.dane.gov.co/index.php/catalog/{ficha}/get-microdata"
    try:
        html = _http(url).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        log(f"ficha {ficha}: no se pudo leer get-microdata: {e}")
        return None
    # Cada botón: ... title="...nofetal2022.zip" ... onclick="...download/23132..."
    for m in re.finditer(r"/download/(\d+)", html):
        ventana = html[max(0, m.start() - 600): m.start() + 200]
        titulos = re.findall(r'title="([^"]+)"|alt="([^"]+)"', ventana)
        etiqueta = " ".join(x for par in titulos for x in par if x).lower()
        if "nofetal" in etiqueta and "fetal2" not in etiqueta.replace("nofetal", ""):
            return int(m.group(1))
    # Respaldo: nombre de recurso 'Defuncionesnofetales' (fichas recientes).
    i = html.lower().find("defuncionesnofetales")
    if i >= 0:
        m = re.search(r"/download/(\d+)", html[max(0, i - 400): i + 400])
        if m:
            return int(m.group(1))
    # Respaldo 2 (fichas antiguas, p.ej. 2019): el archivo se llama 'Defunciones.zip'
    # (sin 'nofetal'); se distingue de 'Fetales.zip' y 'Nacimientos.zip' por el title.
    for m in re.finditer(r"/download/(\d+)", html):
        ventana = html[max(0, m.start() - 600): m.start() + 200].lower()
        if ("defunciones.zip" in ventana
                and "fetales.zip" not in ventana
                and "nacimientos.zip" not in ventana):
            return int(m.group(1))
    log(f"ficha {ficha}: no se encontró el archivo de defunciones no fetales")
    return None


def procesar_zip(data: bytes, cod_dpto: str, cod_munic: str) -> Counter:
    """Agrega defunciones del municipio objetivo por (mes, causa) desde el CSV
    interno del ZIP, leído en streaming (latin-1)."""
    conteo: Counter = Counter()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        nombre = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if not nombre:
            log("el ZIP no contiene CSV")
            return conteo
        with zf.open(nombre) as fh:
            texto = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            r = csv.reader(texto)
            h = next(r)
            ix = {c: i for i, c in enumerate(h)}
            try:
                i_dpto, i_mun, i_mes, i_cau = (
                    ix["COD_DPTO"], ix["COD_MUNIC"], ix["MES"], ix["C_BAS1"])
            except KeyError as e:
                log(f"columna faltante en CSV: {e}")
                return conteo
            dptos = {cod_dpto, cod_dpto.lstrip("0")}
            muns = {cod_munic, cod_munic.lstrip("0")}
            for row in r:
                if len(row) <= i_cau:
                    continue
                if row[i_dpto] in dptos and row[i_mun] in muns:
                    mes = (row[i_mes] or "").strip().zfill(2)
                    if not mes.isdigit():
                        continue
                    causa = (row[i_cau] or "").strip().upper()
                    conteo[(mes, "total")] += 1
                    if causa[:1] == "J":
                        conteo[(mes, "respiratorias")] += 1
                    elif causa[:1] == "I":
                        conteo[(mes, "circulatorias")] += 1
    return conteo


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    dane = cfg.get("dane_eevv")
    if not dane:
        log("No hay sección 'dane_eevv' en sources.yml")
        return 0

    obj = dane["municipio_objetivo"]
    cod_dpto, cod_munic = str(obj["cod_dpto"]), str(obj["cod_munic"])
    base_dl = dane["base_descarga"]

    filas = []          # (anio, mes, causa, defunciones)
    cobertura = {}      # anio -> nº de meses con datos
    for anio, meta in sorted(dane["anios"].items()):
        ficha = meta["ficha"]
        fileid = meta.get("fileid") or resolver_fileid(ficha)
        if not fileid:
            log(f"{anio}: sin fileid resoluble, se omite")
            continue
        url = base_dl.format(ficha=ficha, fileid=fileid)
        try:
            log(f"{anio}: descargando ficha {ficha} fileid {fileid} …")
            data = _http(url)
            log(f"{anio}: {len(data)/1e6:.1f} MB; procesando CSV en streaming …")
            conteo = procesar_zip(data, cod_dpto, cod_munic)
        except Exception as e:  # noqa: BLE001
            log(f"{anio}: error ({e}); se omite")
            continue
        meses = {m for (m, _c) in conteo}
        cobertura[int(anio)] = len(meses)
        for (mes, causa), n in sorted(conteo.items()):
            filas.append({"anio": int(anio), "mes": mes, "causa": causa,
                          "defunciones": int(n)})
        tot = sum(n for (m, c), n in conteo.items() if c == "total")
        log(f"{anio}: {tot} defunciones en {obj['nombre']} ({len(meses)} meses)")

    if not filas:
        log("No se agregó ninguna fila (¿fuente caída o fileids inválidos?).")
        return 0

    salida = OUT / "dane_mortalidad_mensual.csv"
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["anio", "mes", "causa", "defunciones"])
        w.writeheader()
        w.writerows(filas)
    (OUT / "dane_cobertura.json").write_text(
        json.dumps({"municipio": obj, "meses_por_anio": cobertura,
                    "nivel": "municipio de ocurrencia (NO comuna)",
                    "periodicidad": "mensual",
                    "causas": {"respiratorias": "CIE-10 J00-J99",
                               "circulatorias": "CIE-10 I00-I99",
                               "total": "todas las causas"}},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Mortalidad DANE -> {salida} ({len(filas)} filas, "
        f"años {sorted(cobertura)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
