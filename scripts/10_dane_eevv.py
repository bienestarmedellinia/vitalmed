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


def grupo_edad(gru_ed1: str) -> str | None:
    """Mapea GRU_ED1 (quinquenal fino del DANE, '00'..'29') a grupos de ciclo
    vital legibles. Códigos DANE: 00 = menor de 1 hora … 06 = <1 año; 07='1-4';
    08='5-9'; 09='10-14'; 10='15-19'; 11='20-24' … cada +1 = +5 años; 28='105-109';
    29='edad desconocida'. Agrupación por ciclo vital para comparar sin ruido."""
    try:
        g = int(gru_ed1)
    except (TypeError, ValueError):
        return None
    if g <= 6:                 # 00-06: desde <1 hora hasta <1 año
        return "Menores de 1 año"
    if g == 7:                 # 07: 1-4
        return "1 a 4 años"
    if 8 <= g <= 9:            # 08-09: 5-14
        return "5 a 14 años"
    if 10 <= g <= 12:          # 10-12: 15-29
        return "15 a 29 años"
    if 13 <= g <= 15:          # 13-15: 30-44
        return "30 a 44 años"
    if 16 <= g <= 19:          # 16-19: 45-64
        return "45 a 64 años"
    if 20 <= g <= 28:          # 20-28: 65 y más
        return "65 años y más"
    return None                # 29 o desconocido: se excluye (se declara)


def procesar_zip(data: bytes, cod_dpto: str, cod_munic: str) -> tuple[Counter, Counter]:
    """Agrega defunciones del municipio objetivo desde el CSV interno del ZIP
    (streaming, latin-1). Devuelve dos contadores:
      - por (mes, causa): total / respiratorias(J) / circulatorias(I)
      - por (grupo_edad, causa): mismas causas, para comparativo etario
    """
    conteo: Counter = Counter()
    por_edad: Counter = Counter()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        nombre = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if not nombre:
            log("el ZIP no contiene CSV")
            return conteo, por_edad
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
                return conteo, por_edad
            i_ed = ix.get("GRU_ED1")
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
                    cau = ("respiratorias" if causa[:1] == "J"
                           else "circulatorias" if causa[:1] == "I" else None)
                    conteo[(mes, "total")] += 1
                    if cau:
                        conteo[(mes, cau)] += 1
                    # Comparativo por grupo de edad (ciclo vital).
                    ge = grupo_edad(row[i_ed]) if i_ed is not None else None
                    if ge:
                        por_edad[(ge, "total")] += 1
                        if cau:
                            por_edad[(ge, cau)] += 1
    return conteo, por_edad


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
    filas_edad = []     # (anio, grupo_edad, causa, defunciones)
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
            conteo, por_edad = procesar_zip(data, cod_dpto, cod_munic)
        except Exception as e:  # noqa: BLE001
            log(f"{anio}: error ({e}); se omite")
            continue
        meses = {m for (m, _c) in conteo}
        cobertura[int(anio)] = len(meses)
        for (mes, causa), n in sorted(conteo.items()):
            filas.append({"anio": int(anio), "mes": mes, "causa": causa,
                          "defunciones": int(n)})
        for (ge, causa), n in sorted(por_edad.items()):
            filas_edad.append({"anio": int(anio), "grupo_edad": ge, "causa": causa,
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
    # Comparativo por grupo de edad (ciclo vital) — habilita análisis por edad real.
    if filas_edad:
        salida_e = OUT / "dane_mortalidad_edad.csv"
        with open(salida_e, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["anio", "grupo_edad", "causa", "defunciones"])
            w.writeheader()
            w.writerows(filas_edad)
        log(f"Mortalidad por edad -> {salida_e} ({len(filas_edad)} filas)")
    (OUT / "dane_cobertura.json").write_text(
        json.dumps({"municipio": obj, "meses_por_anio": cobertura,
                    "nivel": "municipio de ocurrencia (NO comuna)",
                    "periodicidad": "mensual",
                    "grupos_edad": ["Menores de 1 año", "1 a 4 años", "5 a 14 años",
                                    "15 a 29 años", "30 a 44 años", "45 a 64 años",
                                    "65 años y más"],
                    "causas": {"respiratorias": "CIE-10 J00-J99",
                               "circulatorias": "CIE-10 I00-I99",
                               "total": "todas las causas"}},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Mortalidad DANE -> {salida} ({len(filas)} filas, "
        f"años {sorted(cobertura)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
