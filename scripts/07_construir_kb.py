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
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

BASE = Path(__file__).resolve().parent.parent
TAB = BASE / "outputs" / "tablas"
KB = BASE / "outputs" / "kb"
SOURCES = Path(__file__).resolve().parent / "sources.yml"
MESES_ANIO_COMPLETO = 9      # >= 75% de los meses publicados (criterio SIATA de validez)

NOTA_CORRELACION = (
    "Correlación entre los 21 territorios (no entre personas) y sin ajustar por edad. "
    "La mortalidad bruta es mayor donde la población es más envejecida; por eso puede "
    "asociarse NEGATIVAMENTE con desempleo o inseguridad alimentaria sin que estos "
    "protejan de nada. Con muchos factores probados, alguna asociación puede ser casual. "
    "Asociación no implica causalidad.")


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
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }
    kb["fuentes"] = {
        "ecv": {"nombre": "Encuesta de Calidad de Vida de Medellín",
                "entidad": "Alcaldía de Medellín", "anios": [2022, 2023, 2024, 2025]},
        "medata_salud": {"nombre": "VC_Datos_Enfermedades",
                         "entidad": "Secretaría de Salud de Medellín",
                         "nivel": "comuna", "serie": "2012-2022"},
        "siata": {"nombre": "Datos validados de calidad del aire",
                  "entidad": "SIATA - Valle de Aburrá", "variable": "PM2.5"},
        "dane_eevv": {"nombre": "Estadísticas Vitales (defunciones no fetales)",
                      "entidad": "DANE", "nivel": "municipio (Medellín)",
                      "variable": "mortalidad mensual por causa CIE-10"},
        "sivigila": {"nombre": "SIVIGILA (vigilancia en salud pública)",
                     "entidad": "INS", "nivel": "municipio (Medellín)",
                     "variable": "casos semanales (ESI-IRAG, intento de suicidio)"},
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

    # ── Tasas crudas por componente del índice (para dispersión y simulador) ──
    idx_f = TAB / "indice_priorizacion_comuna.csv"
    idx_kb = kb["indicadores"].get("indice_priorizacion")
    if idx_f.exists() and idx_kb:
        crudas = pd.read_csv(idx_f).set_index("comuna")
        for fila in idx_kb["ranking"]:
            c = int(fila["comuna"])
            if c in crudas.index:
                fila["tasa_mortalidad"] = round(float(crudas.loc[c, "tasa_mortalidad"]), 2)
                fila["tasa_suicidio"] = round(float(crudas.loc[c, "tasa_suicidio"]), 2)
        log("tasas crudas añadidas al índice")

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
        # Comparación interanual: solo estaciones con dato en ambos años.
        previo = df[df["anio"] == anio_ref - 1].set_index("estacion")["media_pm25"]
        comp = [{"estacion": str(r.estacion),
                 "anterior": round(float(previo[r.estacion]), 2),
                 "actual": round(float(r.media_pm25), 2)}
                for r in ref.itertuples() if r.estacion in previo.index]
        if comp:
            kb["indicadores"]["pm25_siata"]["comparacion"] = {
                "anio_anterior": anio_ref - 1, "anio_actual": anio_ref,
                "estaciones": comp}
        log(f"PM2.5 SIATA: {len(ref)} estaciones (año {anio_ref}), "
            f"{len(comp)} comparables con {anio_ref - 1}")

    # ── Mortalidad mensual por causa (DANE Estadísticas Vitales) ──
    dane_f = TAB / "dane_mortalidad_mensual.csv"
    if dane_f.exists():
        dm = pd.read_csv(dane_f, dtype={"mes": str})
        cob_f = TAB / "dane_cobertura.json"
        cob = json.loads(cob_f.read_text(encoding="utf-8")) if cob_f.exists() else {}
        anios = sorted(dm["anio"].unique().tolist())
        # Serie mensual por causa: {causa: {anio: {mes: defunciones}}}
        serie = {}
        for r in dm.itertuples():
            serie.setdefault(r.causa, {}).setdefault(str(int(r.anio)), {})[r.mes] = int(r.defunciones)
        # Totales anuales por causa (contexto rápido).
        tot_anual = (dm.groupby(["causa", "anio"])["defunciones"].sum()
                       .reset_index())
        resumen = {}
        for r in tot_anual.itertuples():
            resumen.setdefault(r.causa, {})[str(int(r.anio))] = int(r.defunciones)
        kb["indicadores"]["mortalidad_dane"] = {
            "unidad": "defunciones (conteo mensual)",
            "nivel": cob.get("nivel", "municipio de ocurrencia (NO comuna)"),
            "municipio": cob.get("municipio", {}),
            "periodicidad": "mensual",
            "anios": anios,
            "causas": cob.get("causas", {}),
            "advertencia": ("Serie mensual municipal (Medellín), no por comuna ni "
                            "diaria. Asociación, no causalidad; sin estandarizar por edad."),
            "serie": serie,
            "total_anual": resumen,
        }
        log(f"Mortalidad DANE: {len(anios)} años {anios}, "
            f"causas {sorted(serie)}")

    # ── SIVIGILA: serie semanal de eventos centinela (INS) ──
    sivi_f = TAB / "sivigila_semanal.csv"
    if sivi_f.exists():
        sv = pd.read_csv(sivi_f)
        cob_f = TAB / "sivigila_cobertura.json"
        cob = json.loads(cob_f.read_text(encoding="utf-8")) if cob_f.exists() else {}
        # Serie semanal por evento: {evento: {anio: {semana: casos}}}
        serie = {}
        tot_anual = {}
        for r in sv.itertuples():
            serie.setdefault(r.evento, {}).setdefault(str(int(r.anio)), {})[str(int(r.semana))] = int(r.casos)
            tot_anual.setdefault(r.evento, {})
            tot_anual[r.evento][str(int(r.anio))] = tot_anual[r.evento].get(str(int(r.anio)), 0) + int(r.casos)
        kb["indicadores"]["sivigila"] = {
            "unidad": "casos (conteo semanal)",
            "nivel": cob.get("nivel", "municipio de ocurrencia (NO comuna)"),
            "municipio": cob.get("municipio", {}),
            "periodicidad": "semanal (semana epidemiológica)",
            "advertencia": cob.get("nota", ""),
            "eventos": cob.get("eventos", {}),
            "serie": serie,
            "total_anual": tot_anual,
        }
        log(f"SIVIGILA: {len(serie)} eventos, años {cob.get('eventos', {})}")

    # ── Series completas por indicador y territorio (todas las fuentes) ──
    series = construir_series()
    if series:
        kb["series"] = series
        log(f"series: {len(series['catalogo'])} indicadores, "
            f"{len(series['correlaciones'])} correlaciones")
        f = kb["fuentes"]
        sal = [c for c in series["catalogo"] if c["fuente"].startswith("MEData")]
        eco = [c for c in series["catalogo"] if c["fuente"].startswith("ECV")]
        if sal:
            f["medata_salud"]["serie"] = (f"{min(c['anios'][0] for c in sal)}-"
                                          f"{max(c['anios'][-1] for c in sal)}")
            f["medata_salud"]["indicadores"] = len(sal)
        if eco:
            f["ecv"]["serie_historica"] = (f"{min(c['anios'][0] for c in eco)}-"
                                           f"{max(c['anios'][-1] for c in eco)}")
            f["ecv"]["indicadores"] = len(eco)

    # ── PM2.5: serie por estación y año de referencia = último año completo ──
    pm = kb["indicadores"].get("pm25_siata")
    if pm and siata_f.exists():
        completar_pm25(pm, pd.read_csv(siata_f), kb)

    salida = KB / "knowledge_base.json"
    contenido = json.dumps(kb, indent=2, ensure_ascii=False)
    salida.write_text(contenido, encoding="utf-8")
    log(f"Knowledge base -> {salida}")

    # Copia para el asistente web estático (GitHub Pages sirve desde docs/).
    docs = BASE / "docs"
    if docs.exists():
        # Versión compacta para la web (mismo contenido, sin espacios).
        compacto = json.dumps(kb, ensure_ascii=False, separators=(",", ":"))
        (docs / "knowledge_base.json").write_text(compacto, encoding="utf-8")
        log("Knowledge base copiado a docs/ (asistente web)")
        exportar_datos_abiertos(kb, docs / "datos")
    return 0


def construir_series() -> dict | None:
    """Catálogo + datos {clave: {valores: {cod: {anio: v}}, casos?, ciudad?}} +
    correlaciones. Claves de territorio y año como texto (JSON)."""
    f_sal, f_ecv = TAB / "salud_comuna_serie.csv", TAB / "ecv_indicadores_serie.csv"
    if not f_sal.exists():
        return None
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    meta_sal = cfg.get("medata", {}).get("indicadores", {})
    sal = pd.read_csv(f_sal)
    territorios = {str(int(c)): str(n) for c, n in
                   sal.drop_duplicates("comuna")[["comuna", "nombre"]].itertuples(index=False)}
    catalogo, datos = [], {}
    # Población implícita por territorio y año (casos / tasa * 100.000). Todas las
    # capas MEData usan los mismos denominadores; se toma la primera capa con dato
    # > 0 para poder agregar también capas con tasa 0 en algún territorio.
    pob = {}
    for r in sal[(sal["tasa"] > 0) & sal["casos"].notna()].itertuples():
        pob.setdefault((int(r.comuna), int(r.anio)), r.casos / r.tasa * 100000)

    for clave, d in sal.groupby("indicador", sort=False):
        m = meta_sal.get(clave, {})
        d = d.dropna(subset=["tasa"])
        valores, casos = {}, {}
        for r in d.itertuples():
            valores.setdefault(str(int(r.comuna)), {})[str(int(r.anio))] = round(float(r.tasa), 2)
            if r.casos == r.casos:
                casos.setdefault(str(int(r.comuna)), {})[str(int(r.anio))] = int(r.casos)
        # Tasa agregada de los 21 territorios: suma de casos / población implícita.
        ciudad = {}
        for anio, g in d.groupby("anio"):
            ps = [pob.get((int(c), int(anio))) for c in g["comuna"]]
            if len(g) == len(territorios) and all(ps) and g["casos"].notna().all():
                ciudad[str(int(anio))] = round(float(g["casos"].sum() / sum(ps) * 100000), 2)
        anios = sorted(int(a) for a in d["anio"].unique())
        catalogo.append({"clave": clave, "nombre": m.get("nombre", clave),
                         "unidad": m.get("unidad", "por 100.000 hab."),
                         "tema": m.get("tema", "salud"), "dimension": "salud",
                         "fuente": "MEData - Secretaría de Salud", "anios": anios})
        datos[clave] = {"valores": valores, "casos": casos}
        if ciudad:
            datos[clave]["ciudad"] = ciudad

    if f_ecv.exists():
        ecv = pd.read_csv(f_ecv)
        cat_ecv = json.loads((TAB / "ecv_catalogo.json").read_text(encoding="utf-8"))
        por_clave = {k: g for k, g in ecv.groupby("indicador")}
        for c in cat_ecv:
            g = por_clave.get(c["clave"])
            if g is None:
                continue
            valores, ciudad = {}, {}
            for r in g.itertuples():
                if int(r.territorio_cod) == 0:
                    ciudad[str(int(r.anio))] = float(r.valor)
                else:
                    valores.setdefault(str(int(r.territorio_cod)), {})[str(int(r.anio))] = float(r.valor)
            catalogo.append({"clave": c["clave"], "nombre": c["nombre"], "unidad": c["unidad"],
                             "tema": c["tema"], "dimension": "social",
                             "fuente": "ECV - serie histórica de indicadores (Planeación)",
                             "anios": sorted(int(a) for a in g["anio"].unique())})
            datos[c["clave"]] = {"valores": valores, "ciudad": ciudad}

    corr = []
    f_corr = TAB / "correlaciones_territoriales.csv"
    if f_corr.exists():
        claves = {c["clave"] for c in catalogo}
        for r in pd.read_csv(f_corr).itertuples():
            if r.factor in claves and r.resultado in claves:
                corr.append({"resultado": r.resultado, "factor": r.factor, "anio": int(r.anio),
                             "n": int(r.n), "pearson": float(r.pearson),
                             "spearman": float(r.spearman), "significativa": bool(r.significativa)})
    return {"territorios": territorios, "catalogo": catalogo, "datos": datos,
            "correlaciones": corr, "nota_correlaciones": NOTA_CORRELACION}


def exportar_datos_abiertos(kb: dict, destino: Path) -> None:
    """Publica TODAS las estadísticas del KB como CSV legibles en docs/datos/
    (módulo de datos independiente del asistente). Se generan desde el KB para
    que las cifras sean idénticas en el explorador, el asistente y las descargas."""
    destino.mkdir(parents=True, exist_ok=True)
    s = kb.get("series") or {}
    terr = s.get("territorios", {})
    cat = {c["clave"]: c for c in s.get("catalogo", [])}
    filas, ciudad = [], []
    for clave, d in (s.get("datos") or {}).items():
        c = cat.get(clave)
        if not c:
            continue
        base = {"dimension": c["dimension"], "tema": c["tema"], "clave": clave,
                "indicador": c["nombre"], "unidad": c["unidad"], "fuente": c["fuente"]}
        for cod, serie in d.get("valores", {}).items():
            for anio, v in serie.items():
                filas.append({**base, "territorio_cod": int(cod), "territorio": terr.get(cod, cod),
                              "anio": int(anio), "valor": v,
                              "casos": (d.get("casos") or {}).get(cod, {}).get(anio)})
        for anio, v in (d.get("ciudad") or {}).items():
            ciudad.append({**base, "anio": int(anio), "valor_medellin": v})
    archivos = {}
    if filas:
        df = pd.DataFrame(filas).sort_values(["dimension", "clave", "anio", "territorio_cod"])
        df["casos"] = df["casos"].astype("Int64")
        archivos["indicadores_por_territorio.csv"] = (
            df, "Todos los indicadores (salud MEData y sociales ECV) por territorio y año.")
    if ciudad:
        archivos["indicadores_medellin.csv"] = (
            pd.DataFrame(ciudad).sort_values(["dimension", "clave", "anio"]),
            "Valor de Medellín por indicador y año (tasa agregada de los 21 territorios o total ECV).")
    if s.get("correlaciones"):
        cr = pd.DataFrame(s["correlaciones"])
        cr.insert(1, "resultado_nombre", cr["resultado"].map(lambda k: cat.get(k, {}).get("nombre", k)))
        cr.insert(3, "factor_nombre", cr["factor"].map(lambda k: cat.get(k, {}).get("nombre", k)))
        archivos["factores_asociados.csv"] = (
            cr, "Correlación entre 21 territorios (Pearson y Spearman). Asociación, no causalidad.")
    pm = kb.get("indicadores", {}).get("pm25_siata") or {}
    if pm.get("serie"):
        p = pd.DataFrame([{"estacion": e, "anio": int(a), "pm25_media_anual": v}
                          for e, x in pm["serie"].items() for a, v in x.items()])
        archivos["pm25_por_estacion.csv"] = (
            p.sort_values(["anio", "estacion"]),
            "PM2.5 media anual por estación SIATA (años completos). No es por comuna.")
    idx = kb.get("indicadores", {}).get("indice_priorizacion") or {}
    if idx.get("ranking"):
        archivos["indice_priorizacion.csv"] = (
            pd.DataFrame(idx["ranking"]), idx.get("descripcion", "Índice de priorización en salud."))
    md = kb.get("indicadores", {}).get("mortalidad_dane") or {}
    if md.get("serie"):
        filas_m = [{"anio": int(a), "mes": mes, "causa": causa, "defunciones": v}
                   for causa, xa in md["serie"].items()
                   for a, xm in xa.items() for mes, v in xm.items()]
        archivos["mortalidad_dane_mensual.csv"] = (
            pd.DataFrame(filas_m).sort_values(["causa", "anio", "mes"]),
            "Mortalidad mensual en Medellín por causa CIE-10 (DANE EEVV). "
            "Nivel municipal (no comuna). respiratorias=J00-J99, circulatorias=I00-I99.")
    sv = kb.get("indicadores", {}).get("sivigila") or {}
    if sv.get("serie"):
        filas_s = [{"evento": ev, "anio": int(a), "semana": int(s), "casos": v}
                   for ev, xa in sv["serie"].items()
                   for a, xs in xa.items() for s, v in xs.items()]
        archivos["sivigila_semanal.csv"] = (
            pd.DataFrame(filas_s).sort_values(["evento", "anio", "semana"]),
            "Casos semanales SIVIGILA en Medellín (INS). ESI-IRAG (respiratorio "
            "centinela) e intento de suicidio. Nivel municipal (no comuna).")
    if cat:
        archivos["catalogo_indicadores.csv"] = (
            pd.DataFrame([{k: (", ".join(map(str, v)) if isinstance(v, list) else v)
                           for k, v in c.items()} for c in cat.values()]),
            "Catálogo: clave, nombre, unidad, tema, dimensión, fuente y años de cada indicador.")
    for nombre, (df, _) in archivos.items():
        df.to_csv(destino / nombre, index=False, encoding="utf-8")
    # Índice de archivos (lo lee el explorador para listar las descargas).
    indice = [{"archivo": n, "descripcion": d, "filas": int(len(df))}
              for n, (df, d) in archivos.items()]
    (destino / "indice.json").write_text(
        json.dumps({"generado_utc": kb.get("meta", {}).get("generado_utc"), "archivos": indice},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"datos abiertos -> {destino} ({len(archivos)} archivos)")


def completar_pm25(pm: dict, df: pd.DataFrame, kb: dict) -> None:
    """Serie por estación, promedio de estaciones por año y año de referencia =
    último año COMPLETO (>= 9 meses publicados y anterior al año en curso)."""
    cob_f = TAB / "siata_cobertura.json"
    meses = {}
    if cob_f.exists():
        meses = {int(a): int(n) for a, n in
                 json.loads(cob_f.read_text(encoding="utf-8"))["meses_por_anio"].items()}
    actual = datetime.now(timezone.utc).year
    completos = sorted(int(a) for a in df["anio"].unique()
                       if meses.get(int(a), 12) >= MESES_ANIO_COMPLETO and int(a) < actual)
    validos = df[(df["meses_validos"] >= MESES_ANIO_COMPLETO) & df["anio"].isin(completos)]
    serie = {}
    for r in validos.itertuples():
        serie.setdefault(str(r.estacion), {})[str(int(r.anio))] = round(float(r.media_pm25), 2)
    prom = {str(int(a)): round(float(g["media_pm25"].mean()), 2)
            for a, g in validos.groupby("anio") if int(a) in completos}
    pm["serie"] = serie
    pm["promedio_estaciones"] = prom
    pm["anios_completos"] = [int(a) for a in completos]
    pm["meses_publicados"] = {str(a): n for a, n in sorted(meses.items())}
    pm["criterio"] = (f"Media anual por estación con >= {MESES_ANIO_COMPLETO} meses válidos "
                      "(cada mes con >= 75% de horas válidas). Año completo: >= "
                      f"{MESES_ANIO_COMPLETO} meses publicados.")
    if completos:
        ref_anio = int(completos[-1])
        ref = validos[validos["anio"] == ref_anio].sort_values("media_pm25", ascending=False)
        pm["anio"] = ref_anio
        pm["ranking"] = [{"estacion": str(r.estacion), "media_pm25": round(float(r.media_pm25), 2),
                          "meses_validos": int(r.meses_validos)} for r in ref.itertuples()]
        previo = validos[validos["anio"] == ref_anio - 1].set_index("estacion")["media_pm25"]
        comp = [{"estacion": str(r.estacion), "anterior": round(float(previo[r.estacion]), 2),
                 "actual": round(float(r.media_pm25), 2)}
                for r in ref.itertuples() if r.estacion in previo.index]
        if comp:
            pm["comparacion"] = {"anio_anterior": ref_anio - 1, "anio_actual": ref_anio,
                                 "estaciones": comp}
        else:
            pm.pop("comparacion", None)
    # Se reporta el rango de años COMPLETOS (los parciales no tienen media anual válida).
    if completos:
        kb["fuentes"]["siata"]["serie"] = f"{completos[0]}-{completos[-1]} (años completos)"
    log(f"PM2.5: años completos {completos}, referencia {pm.get('anio')}")


if __name__ == "__main__":
    sys.exit(main())
