#!/usr/bin/env python3
"""
05_analizar.py — Análisis y hallazgo cuantificado por comuna.

Cruza, a nivel de comuna/corregimiento:
  - MEData · Secretaría de Salud: mortalidad y natalidad (casos y tasa por año)
  - ECV: cobertura muestral social por territorio (de 04_integrar)

Produce un hallazgo principal con cifra y tablas analíticas publicables:
  outputs/tablas/analisis_mortalidad_comuna.csv
  outputs/tablas/hallazgo.json               (cifra principal, para la ficha)
  outputs/tablas/salud_comuna_serie.csv      (10 capas MEData, todos los años)
  outputs/tablas/ecv_indicadores_serie.csv   (serie histórica oficial ECV por territorio)
  outputs/tablas/ecv_catalogo.json           (nombre, unidad, tema y notas de cada indicador ECV)
  outputs/tablas/correlaciones_territoriales.csv (factores asociados, entre territorios)

Se ejecuta en GitHub Actions. Datos agregados por comuna, sin PII.
"""
from __future__ import annotations
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import yaml

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
OUT = BASE / "outputs" / "tablas"

ANIO_REF = 2022          # último año disponible en MEData salud
ANIO_INI = 2012          # inicio de la serie (mortalidad)
SOURCES = Path(__file__).resolve().parent / "sources.yml"
SERIE_ECV = RAW / "ecv_2022" / "serie.xlsx"   # Serie histórica oficial de indicadores ECV
MIN_TERRITORIOS_CORR = 15                    # mínimo de territorios para correlacionar

# Territorios válidos: 16 comunas + 5 corregimientos. Excluye códigos
# residuales de la fuente como 99 = "Sin información de comuna".
TERRITORIOS_VALIDOS = set(range(1, 17)) | {50, 60, 70, 80, 90}


def log(msg: str) -> None:
    print(f"[analizar] {msg}", flush=True)


def cargar_salud(nombre: str, prefijo_casos: str) -> pd.DataFrame:
    """Carga una capa de salud MEData en formato largo (comuna, anio, casos, tasa)."""
    f = RAW / "medata" / f"{nombre}.csv"
    df = pd.read_csv(f)
    # 'comuna' viene como '01'..'16'; filtramos solo comunas numéricas.
    df["comuna"] = pd.to_numeric(df["comuna"], errors="coerce")
    df = df.dropna(subset=["comuna"])
    df["comuna"] = df["comuna"].astype(int)
    # Mantener solo los 21 territorios oficiales (excluye 99 "Sin información").
    df = df[df["comuna"].isin(TERRITORIOS_VALIDOS)].copy()

    registros = []
    anios = sorted({int(m) for c in df.columns for m in re.findall(r"_(\d{4})$", c)})
    for anio in anios:
        col_casos = f"{prefijo_casos}_{anio}"
        col_tasa = f"tasa_{anio}"
        if col_casos not in df.columns or col_tasa not in df.columns:
            continue
        tmp = df[["comuna", "nombre", col_casos, col_tasa]].copy()
        tmp.columns = ["comuna", "nombre", "casos", "tasa"]
        tmp["anio"] = anio
        registros.append(tmp)
    largo = pd.concat(registros, ignore_index=True)
    largo["evento"] = nombre
    return largo


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# ── Todas las capas MEData en formato largo ─────────────────────────
def serie_salud(cfg_ind: dict) -> pd.DataFrame:
    partes = []
    for clave, meta in cfg_ind.items():
        if not (RAW / "medata" / f"{clave}.csv").exists():
            log(f"MEData {clave}: no descargado, se omite")
            continue
        d = cargar_salud(clave, meta.get("casos", "casos"))
        d["indicador"] = clave
        partes.append(d)
        log(f"MEData {clave}: {d['comuna'].nunique()} territorios, "
            f"{d['anio'].min()}-{d['anio'].max()}")
    if not partes:
        return pd.DataFrame()
    out = pd.concat(partes, ignore_index=True)
    return out[["indicador", "comuna", "nombre", "anio", "casos", "tasa"]]


# ── Serie histórica oficial de indicadores ECV (Planeación) ─────────
def _es_anio(v) -> int | None:
    s = str(v).strip() if v is not None else ""
    if re.fullmatch(r"(19|20)\d{2}(\.0)?", s):
        return int(float(s))
    return None


def _unidad_ecv(titulo: str) -> str:
    t = _norm(titulo)
    if "masculinidad" in t:
        return "hombres por cada 100 mujeres"
    if "por 100 personas" in t:
        return "por cada 100 personas"
    if "porcentaje" in t:
        return "%"
    return ""


def _tema_ecv(nombre: str) -> str:
    t = _norm(nombre)
    for claves, tema in (
            (("planific",), "salud sexual y reproductiva"),
            (("inseguridad alimentaria",), "seguridad alimentaria"),
            (("deport", "recreativ", "ludic", "cultural"), "deporte y cultura"),
            (("escolar", "desercion", "analfabet"), "educación"),
            (("desempleo", "ocupacion", "participacion"), "empleo"),
            (("dependencia", "masculinidad"), "demografía"),
            (("jefe",), "hogares")):
        if any(c in t for c in claves):
            return tema
    return "condiciones de vida"


def _limpiar_nombre(titulo: str) -> str:
    t = re.sub(r"^T\d+\s*=\s*", "", titulo.strip())
    t = re.sub(r"\s*,00\s*$", "", t)
    t = re.sub(r"\((por 100 personas|porcentaje|p)\)?\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*\(por 100 personas\)", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" .")


def _slug(nombre: str) -> str:
    vacias = {"de", "la", "el", "los", "las", "que", "con", "o", "y", "en", "a",
              "del", "porcentaje", "por", "nivel", "algun", "tienen", "sobre"}
    pal = [w for w in re.split(r"[^a-z0-9]+", _norm(nombre)) if w and w not in vacias]
    return "ecv_" + "_".join(pal)[:48].rstrip("_")


def serie_ecv() -> tuple[pd.DataFrame, list]:
    """Lee las dos hojas de la serie histórica y devuelve (largo, catálogo).

    Reglas (documentadas en el catálogo):
      - Se excluyen indicadores cuya nota técnica de la fuente dice "no publicar".
      - Si un año aparece en dos versiones (p. ej. 2021 y "2021 UDEA"), ese año se
        excluye por ambiguo (la fuente indica que la metodología difiere).
      - Territorio 0 = Total Medellín.
    """
    if not SERIE_ECV.exists():
        log("Serie histórica ECV no descargada: se omite")
        return pd.DataFrame(), []
    import openpyxl
    wb = openpyxl.load_workbook(SERIE_ECV, read_only=True, data_only=True)
    filas, catalogo, vistos = [], [], {}
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True, max_col=40)]
        titulo_t, codigo_t = None, None
        i = 0
        while i < len(rows):
            r = rows[i]
            c0 = r[0] if r else None
            if isinstance(c0, str) and re.match(r"^T\d+\s*=", c0.strip()):
                titulo_t = c0.strip()
                codigo_t = re.match(r"^T(\d+)", c0.strip()).group(1)
            anios_col = {j: _es_anio(v) for j, v in enumerate(r[1:], start=1)}
            n_anios = sum(1 for a in anios_col.values() if a)
            if not (isinstance(c0, str) and n_anios >= 3):
                i += 1
                continue
            es_tabla = c0.strip().lower().startswith("tabla")
            titulo = titulo_t if es_tabla and titulo_t else c0.strip()
            codigo = codigo_t if es_tabla else None
            etiquetas = [str(v).strip() for v in r[1:] if v is not None]
            ambiguos = {a for a in anios_col.values() if a and
                        sum(1 for e in etiquetas if e.startswith(str(a))) > 1}
            notas = [str(v).strip() for v in r[1:]
                     if isinstance(v, str) and len(v.strip()) > 25]
            excluir = any("no publicar" in _norm(n) for n in notas)
            j, datos = i + 1, []
            while j < len(rows) and rows[j] and isinstance(rows[j][0], str):
                t0 = rows[j][0].strip()
                m = re.match(r"^(\d{1,2})\.\s*", t0)
                cod = int(m.group(1)) if m else (0 if t0.lower() == "total" else None)
                if cod is None and not t0.lower().startswith("total"):
                    break
                if cod is not None and (cod == 0 or cod in TERRITORIOS_VALIDOS):
                    for col, anio in anios_col.items():
                        v = rows[j][col] if col < len(rows[j]) else None
                        if anio and anio not in ambiguos and isinstance(v, (int, float)) \
                                and not isinstance(v, bool) and v == v:
                            datos.append((cod, anio, round(float(v), 2)))
                j += 1
            i = j
            nombre = _limpiar_nombre(titulo)
            if excluir or not datos:
                log(f"ECV excluido ({'nota técnica: no publicar' if excluir else 'sin datos'}): {nombre}")
                continue
            clave = f"ecv_t{codigo}" if codigo else _slug(nombre)
            ultimo = max(a for _, a, _ in datos)
            previo = vistos.get(_norm(nombre))
            if previo and previo[1] >= ultimo:
                continue  # duplicado entre hojas: se conserva la serie más reciente
            if previo:
                filas = [f for f in filas if f[0] != previo[0]]
                catalogo = [c for c in catalogo if c["clave"] != previo[0]]
            vistos[_norm(nombre)] = (clave, ultimo)
            catalogo.append({"clave": clave, "nombre": nombre, "unidad": _unidad_ecv(titulo),
                             "tema": _tema_ecv(nombre), "hoja": ws.title,
                             "nota_tecnica": " ".join(notas)[:400],
                             "anios_excluidos_ambiguos": sorted(ambiguos)})
            filas += [(clave, c, a, v) for c, a, v in datos]
    wb.close()
    largo = pd.DataFrame(filas, columns=["indicador", "territorio_cod", "anio", "valor"])
    # Control de calidad: en algunas tablas de la fuente los valores por territorio
    # SUMAN el total de Medellín (son aportes al total, no tasas del territorio) y
    # no se pueden comparar entre territorios. Se detecta y se excluye.
    aditivos = []
    for clave, g in largo.groupby("indicador"):
        tot = g[g["territorio_cod"] == 0].set_index("anio")["valor"]
        suma = g[g["territorio_cod"] != 0].groupby("anio")["valor"].sum()
        razon = (suma / tot).replace([float("inf")], float("nan")).dropna()
        if len(razon) and any(abs(razon.median() - k) < 0.03 * k for k in (1, 10)):
            aditivos.append(clave)
    for clave in aditivos:
        nombre = next(c["nombre"] for c in catalogo if c["clave"] == clave)
        log(f"ECV excluido (valores por territorio suman el total: no son tasas comparables): {nombre}")
    largo = largo[~largo["indicador"].isin(aditivos)]
    catalogo = [c for c in catalogo if c["clave"] not in aditivos]
    log(f"ECV serie histórica: {len(catalogo)} indicadores, {len(largo)} valores")
    return largo, catalogo


# ── Factores asociados: correlación entre territorios ───────────────
def correlaciones(salud: pd.DataFrame, ecv: pd.DataFrame) -> pd.DataFrame:
    """Pearson y Spearman entre cada factor y cada resultado de salud, en el año
    más reciente con >= MIN_TERRITORIOS_CORR territorios en ambos. Describe la
    asociación ENTRE TERRITORIOS (no individual, no causal)."""
    tablas = {}
    if not salud.empty:
        for k, d in salud.groupby("indicador"):
            tablas[k] = d.pivot_table(index="comuna", columns="anio", values="tasa")
    if not ecv.empty:
        e = ecv[ecv["territorio_cod"] != 0]
        for k, d in e.groupby("indicador"):
            tablas[k] = d.pivot_table(index="territorio_cod", columns="anio", values="valor")
    out = []
    for res in ("mortalidad", "intento_suicidio"):
        if res not in tablas:
            continue
        y_t = tablas[res]
        for fac, x_t in tablas.items():
            if fac == res:
                continue
            for anio in sorted(set(y_t.columns) & set(x_t.columns), reverse=True):
                par = pd.concat([x_t[anio], y_t[anio]], axis=1, join="inner").dropna()
                if len(par) < MIN_TERRITORIOS_CORR or par.iloc[:, 0].nunique() < 3:
                    continue
                n = len(par)
                p = par.iloc[:, 0].corr(par.iloc[:, 1])
                # Spearman = Pearson sobre rangos (sin depender de scipy).
                s = par.iloc[:, 0].rank().corr(par.iloc[:, 1].rank())
                if p != p or s != s:
                    break
                r_crit = math.tanh(1.96 / math.sqrt(n - 3))
                out.append({"resultado": res, "factor": fac, "anio": int(anio), "n": n,
                            "pearson": round(float(p), 3), "spearman": round(float(s), 3),
                            "r_critico_95": round(r_crit, 3),
                            "significativa": bool(abs(p) >= r_crit and abs(s) >= r_crit
                                                  and (p > 0) == (s > 0))})
                break
    df = pd.DataFrame(out)
    if not df.empty:
        df = df.reindex(df["pearson"].abs().sort_values(ascending=False).index)
        log(f"correlaciones: {len(df)} pares, {int(df['significativa'].sum())} significativas (aprox. 95%)")
    return df


def _norm_minmax(s: pd.Series) -> pd.Series:
    """Normaliza una serie a 0-100 (min-max). Si no hay rango, devuelve 0."""
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series([0.0] * len(s), index=s.index)
    return (s - lo) / (hi - lo) * 100


def _indice_priorizacion(mort: pd.DataFrame) -> pd.DataFrame | None:
    """Índice multivariable de priorización en salud por comuna (año ref).

    Combina dos indicadores MEData por comuna, ambos del año de referencia:
      - mortalidad general (tasa)
      - intento de suicidio (tasa)   -> salud mental
    Normaliza cada uno a 0-100 (min-max) y promedia. Mayor = más prioritario.
    Si la segunda capa no está disponible, retorna None (no se inventa índice).
    """
    f_sui = RAW / "medata" / "intento_suicidio.csv"
    if not f_sui.exists():
        log("intento_suicidio.csv no disponible: se omite índice multivariable")
        return None
    sui = cargar_salud("intento_suicidio", "casos")
    sui_ref = sui[sui["anio"] == ANIO_REF][["comuna", "tasa"]].rename(
        columns={"tasa": "tasa_suicidio"})
    mort_ref = mort[mort["anio"] == ANIO_REF][
        ["comuna", "nombre", "tasa"]].rename(columns={"tasa": "tasa_mortalidad"})

    df = mort_ref.merge(sui_ref, on="comuna", how="inner")
    if df.empty:
        log("sin intersección de comunas para el índice; se omite")
        return None

    df["n_mortalidad"] = _norm_minmax(df["tasa_mortalidad"]).round(1)
    df["n_suicidio"] = _norm_minmax(df["tasa_suicidio"]).round(1)
    df["indice"] = ((df["n_mortalidad"] + df["n_suicidio"]) / 2).round(1)
    df = df.sort_values("indice", ascending=False).reset_index(drop=True)
    df["ranking"] = df.index + 1
    return df[["ranking", "comuna", "nombre", "tasa_mortalidad",
               "tasa_suicidio", "n_mortalidad", "n_suicidio", "indice"]]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    mort = cargar_salud("mortalidad", "casos")
    log(f"mortalidad: {mort['comuna'].nunique()} comunas, "
        f"años {mort['anio'].min()}-{mort['anio'].max()}")

    # ── Hallazgo 1: ranking de mortalidad por comuna en el año de referencia ──
    ref = (mort[mort["anio"] == ANIO_REF]
           .sort_values("tasa", ascending=False)
           .reset_index(drop=True))
    top = ref.iloc[0]
    bottom = ref.iloc[-1]
    brecha = top["tasa"] / bottom["tasa"] if bottom["tasa"] else float("nan")

    # ── Hallazgo 2: evolución 2012 -> 2022 de la comuna más afectada ──
    serie_top = mort[mort["comuna"] == int(top["comuna"])].sort_values("anio")
    t_ini = serie_top[serie_top["anio"] == ANIO_INI]["tasa"]
    t_fin = serie_top[serie_top["anio"] == ANIO_REF]["tasa"]
    var_pct = None
    if len(t_ini) and len(t_fin) and float(t_ini.iloc[0]):
        var_pct = (float(t_fin.iloc[0]) / float(t_ini.iloc[0]) - 1) * 100

    # ── Tabla analítica publicable (ranking de mortalidad) ──
    ref.to_csv(OUT / "analisis_mortalidad_comuna.csv", index=False, encoding="utf-8")

    # ── Índice multivariable de priorización en salud por comuna ──
    # Combina dos indicadores de salud pública (misma fuente MEData, mismo
    # nivel territorial = comuna) normalizados min-max a 0-100 y promediados.
    # Mayor índice = mayor prioridad de intervención. Honesto: solo se
    # combinan dimensiones realmente medidas por comuna (NO se mete PM2.5,
    # que es por estación; eso se reporta como contexto ambiental aparte).
    indice = _indice_priorizacion(mort)
    if indice is not None:
        indice.to_csv(OUT / "indice_priorizacion_comuna.csv",
                      index=False, encoding="utf-8")
        log(f"índice de priorización: {len(indice)} comunas "
            f"(top: {indice.iloc[0]['nombre']} = "
            f"{indice.iloc[0]['indice']})")

    # ── Series completas: todas las capas MEData + serie histórica ECV ──
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    salud = serie_salud(cfg.get("medata", {}).get("indicadores", {}))
    if not salud.empty:
        salud.to_csv(OUT / "salud_comuna_serie.csv", index=False, encoding="utf-8")
    ecv, catalogo_ecv = serie_ecv()
    if not ecv.empty:
        ecv.to_csv(OUT / "ecv_indicadores_serie.csv", index=False, encoding="utf-8")
        (OUT / "ecv_catalogo.json").write_text(
            json.dumps(catalogo_ecv, indent=2, ensure_ascii=False), encoding="utf-8")
    corr = correlaciones(salud, ecv)
    if not corr.empty:
        corr.to_csv(OUT / "correlaciones_territoriales.csv", index=False, encoding="utf-8")

    hallazgo = {
        "evento": "mortalidad general",
        "fuente": "MEData - Secretaría de Salud de Medellín (VC_Datos_Enfermedades)",
        "anio_referencia": ANIO_REF,
        "unidad_tasa": "defunciones por 100.000 habitantes",
        "comuna_mayor_tasa": {
            "comuna": int(top["comuna"]),
            "nombre": str(top["nombre"]),
            "tasa": round(float(top["tasa"]), 2),
            "casos": int(top["casos"]),
        },
        "comuna_menor_tasa": {
            "comuna": int(bottom["comuna"]),
            "nombre": str(bottom["nombre"]),
            "tasa": round(float(bottom["tasa"]), 2),
            "casos": int(bottom["casos"]),
        },
        "brecha_veces": round(float(brecha), 2),
        "variacion_pct_2012_2022_comuna_top": (
            round(var_pct, 1) if var_pct is not None else None),
        "serie_temporal_comuna_top": {
            "anios": [int(a) for a in serie_top["anio"].tolist()],
            "tasas": [round(float(t), 2) for t in serie_top["tasa"].tolist()],
        },
    }
    if indice is not None:
        hallazgo["indice_priorizacion"] = {
            "descripcion": ("Índice multivariable de priorización en salud por "
                            "comuna: promedio de la mortalidad general y el intento "
                            "de suicidio (tasas por 100.000 hab.), cada indicador "
                            "normalizado 0-100 (min-max). Mayor = más prioritario."),
            "fuente": "MEData - Secretaría de Salud de Medellín",
            "anio": ANIO_REF,
            "componentes": ["mortalidad general", "intento de suicidio"],
            "ranking": [
                {"comuna": int(r.comuna), "nombre": str(r.nombre),
                 "indice": round(float(r.indice), 1),
                 "n_mortalidad": round(float(r.n_mortalidad), 1),
                 "n_suicidio": round(float(r.n_suicidio), 1)}
                for r in indice.itertuples()
            ],
        }
    (OUT / "hallazgo.json").write_text(
        json.dumps(hallazgo, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Mensaje de hallazgo (el que va a la ficha / pitch) ──
    print("\n" + "=" * 64)
    log("HALLAZGO PRINCIPAL")
    print(f"  En {ANIO_REF}, la comuna con mayor tasa de mortalidad fue "
          f"{hallazgo['comuna_mayor_tasa']['nombre']} "
          f"(comuna {hallazgo['comuna_mayor_tasa']['comuna']}) con "
          f"{hallazgo['comuna_mayor_tasa']['tasa']} "
          f"defunciones por 100.000 hab.")
    print(f"  Es {hallazgo['brecha_veces']}x la de la comuna con menor tasa "
          f"({hallazgo['comuna_menor_tasa']['nombre']}: "
          f"{hallazgo['comuna_menor_tasa']['tasa']}).")
    if var_pct is not None:
        print(f"  Entre {ANIO_INI} y {ANIO_REF} su tasa varió {var_pct:+.1f}%.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
