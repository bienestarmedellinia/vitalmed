#!/usr/bin/env python3
"""
asistente/motor.py — Motor determinista del asistente (fase 2).

PARIDAD con docs/asistente.js: misma lógica y mismos textos (test_motor.py
compara ambas salidas cuando hay `node` disponible).

Interpreta preguntas en lenguaje natural mediante reglas y responde SOLO con
cifras del knowledge base generado por el pipeline. NO usa IA ni requiere
conexión. Cubre todas las series del KB: indicadores de salud MEData por
comuna, serie histórica de indicadores ECV y PM2.5 por estación (SIATA).

Contrato de respuesta (dataclass Respuesta):
  respuesta_directa, evidencia (indicador, valor, anio, territorio, fuente),
  interpretacion, recomendacion, limitaciones, encontrado
"""
from __future__ import annotations
import json
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
KB_PATH = BASE / "outputs" / "kb" / "knowledge_base.json"
F_MEDATA = "MEData - Secretaría de Salud"


@dataclass
class Respuesta:
    respuesta_directa: str
    evidencia: list = field(default_factory=list)
    interpretacion: str = ""
    recomendacion: str = ""
    limitaciones: str = ""
    encontrado: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ── Utilidades (idénticas en asistente.js) ─────────────────────────
def _norm(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _limpio(q: str) -> str:
    return " " + re.sub(r" +", " ", re.sub(r"[^a-z0-9. ]", " ", _norm(q))).strip() + " "


def _tiene(qn: str, arr) -> bool:
    return any(w in qn for w in arr)


def num(x) -> str:
    """Número con hasta 2 decimales, sin ceros sobrantes."""
    if float(x).is_integer():
        return str(int(x))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _fx(x, d: int) -> str:
    return f"{x:.{d}f}"


def _signo(x, d: int) -> str:
    return ("+" if x > 0 else "") + f"{x:.{d}f}"


def _mediana(vals: list) -> float:
    v = sorted(vals)
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def _capital(s: str) -> str:
    return s[:1].upper() + s[1:]


KW_TENDENCIA = ["evolucion", "evoluciono", "tendencia", "vario", "cambio", "aumento",
                "disminuyo", "entre 2012", "historico", "historia", "mejorado", "empeor",
                "2012 y", "cambiad", "con los anos", "a lo largo", "en el tiempo", "serie"]
KW_AYUDA = ["que preguntas", "que puedo preguntar", "que te puedo", "que le puedo",
            "ayuda", "que sabes", "que puedes", "como funciona", "que informacion",
            "que datos tienes", "que datos hay", "que temas", "como te uso", "como se usa",
            "ejemplos de preguntas", "menu", "hola", "buenas", "que haces"]
KW_AIRE = ["aire", "contaminacion", "pm2.5", "pm25", "pm 2.5", "particulas",
           "ambiental", "calidad del aire", "polucion", "siata", "respirar", "respira", "smog"]
KW_FACTORES = ["factores", "asociad", "se relaciona", "relacionad", "correlac",
               "que influye", "influencia", "determinantes", "explica"]

SINONIMOS = [
    ("intento_suicidio", ["suicid", "salud mental"]),
    ("violencia_genero", ["violencia de genero", "violencia genero", "violencia contra la mujer",
                          "violencia contra las mujeres"]),
    ("tuberculosis_pulmonar", ["tuberculosis"]),
    ("hepatitis_a", ["hepatitis"]),
    ("parotiditis", ["parotiditis", "paperas"]),
    ("tosferina", ["tosferina", "tos ferina"]),
    ("varicela", ["varicela"]),
    ("dengue", ["dengue"]),
    ("natalidad", ["natalidad", "nacimiento", "nacidos", "nacen", "fecundidad"]),
    ("mortalidad", ["mortalidad", "moratilidad", "mortalid", "defuncion", "muerte", "mueren",
                    "muere", "murieron", "fallec"]),
]
ALIAS_ECV = [
    (["desemple", "sin empleo", "paro"], "desempleo abierto"),
    (["hambre", "inseguridad alimentaria", "comida", "alimentacion"],
     "algun nivel de inseguridad alimentaria"),
    (["analfabet", "leer y escribir"], "analfabetismo de 15 y mas"),
    (["escolaridad", "educacion", "estudian", "colegio"], "neta de escolaridad todos los niveles"),
    (["dependencia"], "dependencia economica"),
    (["ocupacion", "empleo", "trabajo"], "tasa ocupacion"),
    (["deporte", "deportiv", "ejercicio", "actividad fisica"], "practica actividades deportivas"),
    (["cultura"], "programas culturales"),
    (["planificacion", "anticoncep", "planifica"], "que planifica"),
    (["masculinidad"], "masculinidad"),
    (["jefas de hogar", "mujeres cabeza", "jefatura femenina"], "mujeres jefes cabeza de hogar"),
]
VACIAS = {"comuna", "comunas", "territorio", "territorios", "barrio", "medellin",
          "ciudad", "datos", "tasa", "tasas", "porcentaje", "poblacion", "personas", "hogares",
          "hogar", "indicador", "indicadores", "cuanto", "cuantos", "cuales", "donde", "tiene",
          "tienen", "entre", "sobre", "segun", "valor", "valores", "nivel", "niveles", "mayor",
          "menor", "total", "sabemos", "situacion", "informacion", "quiero", "saber", "puedo",
          "preguntar", "preguntas", "corregimiento", "corregimientos", "comparar", "compara",
          "priorizar", "salud", "general", "cuanta", "cuantas", "estado", "como", "esta", "estan",
          "fueron", "hubo", "habia", "grave", "jefes", "calificado", "informante", "anos", "cada"}

SIN_CAUSA = ("Los datos del proyecto no incluyen la causa específica de las defunciones "
             "(no hay desagregación por causa ni por edad), por lo que no puedo afirmar "
             "qué las causa. ")
SIN_CAUSA_GEN = ("Los datos del proyecto describen cuánto ocurre en cada territorio, no por "
                 "qué ocurre, así que no puedo afirmar causas. ")
REC_CAUSAS = ("Para identificar causas: pedir a MEData/Secretaría de Salud las defunciones por "
              "causa (CIE-10) y grupo de edad por comuna, y estandarizar las tasas por edad.")
LIM_PIPELINE = "El asistente solo responde con cifras del pipeline."


def detectar_intencion(q: str) -> str:
    qn = _norm(q)
    # El orden importa: específicas antes que genéricas (idéntico a asistente.js).
    if _tiene(qn, KW_AYUDA):
        return "ayuda"
    if _tiene(qn, ["hallazgo", "conclusion principal", "resultado principal", "descubrimiento"]):
        return "hallazgo"
    if _tiene(qn, KW_AIRE):
        return "ambiental"
    if _tiene(qn, KW_FACTORES):
        return "factores"
    if _tiene(qn, ["tres territorios", "3 territorios", "presupuesto",
                   "intervenir", "invertir", "priorizar", "priorizacion"]):
        return "priorizacion"
    if _tiene(qn, KW_TENDENCIA):
        return "tendencia"
    if _tiene(qn, ["fuente", "de donde", "datos reales", "licencia"]):
        return "fuentes"
    if _tiene(qn, ["menor", "mas baja", "mejor", "menos"]):
        return "ranking_bottom"
    if _tiene(qn, ["mayor", "mas alta", "peor", "atencion", "mayores necesidades",
                   "cuales comunas", "ranking", "mas casos"]):
        return "ranking_top"
    return "desconocida"


def pide_causa(q: str) -> bool:
    return _tiene(_norm(q), ["causa", "por que", "porque", "motivo", "razon", "se debe", "origen"])


def detectar_anios(q: str) -> list:
    out = []
    for m in re.finditer(r"\b(?:19|20)\d{2}\b", _norm(q)):
        n = int(m.group(0))
        if n not in out:
            out.append(n)
    return out


def _palabras(t: str) -> list:
    return [w for w in re.split(r"[^a-z0-9]+", _norm(t)) if len(w) >= 5 and w not in VACIAS]


def _aliases(nombre: str) -> list:
    """Variantes del nombre de un territorio (igual que aliasesTerritorio en JS)."""
    n = _norm(nombre)
    out = [n]
    sin_art = re.sub(r"^(la|el|los|las) ", "", n)
    sin_corr = re.sub(r"^corregimiento de ", "", sin_art)
    out += [sin_art, sin_corr, re.sub(r"^san sebastian de ", "", sin_corr)]
    if "laureles" in n:
        out += ["laureles", "estadio"]
    if "candelaria" in n:
        out.append("el centro")
    if "doce de octubre" in n:
        out.append("12 de octubre")
    if "villa hermosa" in n:
        out.append("villahermosa")
    vistos = []
    for a in out:
        if a not in vistos:
            vistos.append(a)
    return [a for a in vistos if len(a) >= 4]


class MotorAsistente:
    def __init__(self, kb_path: Path = KB_PATH):
        self.kb_path = kb_path
        self.kb = self._cargar()

    def _cargar(self) -> dict:
        if not self.kb_path.exists():
            return {}
        return json.loads(self.kb_path.read_text(encoding="utf-8"))

    # ── Acceso al KB ───────────────────────────────────────────────
    def _s(self) -> dict | None:
        return self.kb.get("series")

    def catalogo(self) -> list:
        return (self._s() or {}).get("catalogo", [])

    def info(self, clave):
        return next((c for c in self.catalogo() if c["clave"] == clave), None)

    def datos(self, clave):
        return (self._s() or {}).get("datos", {}).get(clave)

    def ranking_mort(self) -> list:
        return self.kb.get("indicadores", {}).get("mortalidad_2022", {}).get("ranking", [])

    def territorios(self) -> list:
        t = (self._s() or {}).get("territorios")
        if t:
            return [{"cod": c, "nombre": t[c]} for c in sorted(t, key=int)]
        return [{"cod": str(x["comuna"]), "nombre": x["nombre"]} for x in self.ranking_mort()]

    def nombre_terr(self, cod) -> str:
        return next((t["nombre"] for t in self.territorios() if t["cod"] == str(cod)), str(cod))

    @staticmethod
    def es_salud(c) -> bool:
        return c.get("dimension") == "salud"

    def etiqueta(self, c) -> str:
        return "tasa de " + c["nombre"] if self.es_salud(c) else c["nombre"][:1].lower() + c["nombre"][1:]

    def nombre_corto(self, c) -> str:
        return c["nombre"] if self.es_salud(c) else c["nombre"][:1].lower() + c["nombre"][1:]

    def valores_anio(self, clave, anio) -> list:
        d = self.datos(clave)
        if not d:
            return []
        a, out = str(anio), []
        for t in self.territorios():
            v = d["valores"].get(t["cod"], {}).get(a)
            if v is not None:
                cs = d.get("casos", {}).get(t["cod"], {}).get(a) if d.get("casos") else None
                out.append({"cod": t["cod"], "nombre": t["nombre"], "valor": v, "casos": cs})
        return sorted(out, key=lambda x: (-x["valor"], int(x["cod"])))

    def resolver_anio(self, c, pedido):
        anios = c["anios"]
        ult = anios[-1]
        if pedido is None:
            return ult, ""
        if pedido in anios:
            return pedido, ""
        if pedido > ult:
            usado = ult
        elif pedido < anios[0]:
            usado = anios[0]
        else:
            usado = ult
            for a in anios:
                if abs(a - pedido) < abs(usado - pedido):
                    usado = a
        extra = f" (MEData publica estas series por comuna hasta {ult})" if self.es_salud(c) else ""
        return usado, (f"{_capital(c['nombre'])} tiene datos de {anios[0]} a {ult}{extra}; "
                       f"no hay dato para {pedido}. Muestro {usado}. ")

    def limitacion(self, c) -> str:
        if self.es_salud(c):
            return "Tasas brutas, sin estandarizar por edad; asociación, no causalidad."
        return ("Estimación por encuesta (muestra): diferencias pequeñas entre territorios "
                "pueden no ser significativas. Asociación, no causalidad.")

    def fuente_de(self, c) -> str:
        return F_MEDATA if self.es_salud(c) else "ECV - serie histórica (Planeación)"

    # ── Detección dependiente del KB ───────────────────────────────
    def detectar_indicador(self, q: str):
        qn, cat = _norm(q), self.catalogo()
        if _tiene(qn, KW_AIRE):
            return "pm25"
        por_nombre = sorted((c for c in cat if _norm(c["nombre"]) in qn),
                            key=lambda c: -len(c["nombre"]))
        if por_nombre:
            return por_nombre[0]["clave"]
        for clave, ws in SINONIMOS:
            if _tiene(qn, ws) and self.info(clave):
                return clave
        for ws, frag in ALIAS_ECV:
            if not _tiene(qn, ws):
                continue
            c = next((x for x in cat if not self.es_salud(x) and frag in _norm(x["nombre"])), None)
            if c:
                return c["clave"]
        raices = []
        for w in _palabras(q):
            if w[:5] not in raices:
                raices.append(w[:5])
        if not raices:
            return None
        mejor, puntos = None, 0
        for c in cat:
            if self.es_salud(c):
                continue
            p = {w[:5] for w in _palabras(c["nombre"])}
            n = sum(1 for r in raices if r in p)
            if n > puntos or (n == puntos and n > 0 and len(c["nombre"]) < len(mejor["nombre"])):
                mejor, puntos = c, n
        return mejor["clave"] if puntos > 0 else None

    def territorios_en(self, q: str) -> list:
        qn = _limpio(q).replace(".", " ")
        hallados = []
        for t in self.territorios():
            pos, largo = -1, 0
            for a in _aliases(t["nombre"]):
                p = qn.find(" " + a + " ")
                if p >= 0 and len(a) > largo:
                    pos, largo = p, len(a)
            m = re.search(r" (comuna|corregimiento) " + t["cod"] + " ", qn)
            if m and pos < 0:
                pos, largo = m.start(), len(m.group(0))
            if pos >= 0:
                hallados.append({"cod": t["cod"], "pos": pos, "largo": largo})
        hallados.sort(key=lambda h: -h["largo"])
        return [h["cod"] for h in sorted(hallados[:2], key=lambda h: h["pos"])]

    # ── Respuestas ─────────────────────────────────────────────────
    def _no(self, texto: str) -> Respuesta:
        return Respuesta(texto, encontrado=False, limitaciones=LIM_PIPELINE)

    def asociados(self, clave, maximo: int) -> dict:
        corr = (self._s() or {}).get("correlaciones", [])
        lista = [{"otro": x["factor"], "r": x["pearson"], "anio": x["anio"], "n": x["n"],
                  "sig": x["significativa"]} for x in corr if x["resultado"] == clave]
        if not lista:
            lista = [{"otro": x["resultado"], "r": x["pearson"], "anio": x["anio"], "n": x["n"],
                      "sig": x["significativa"]} for x in corr if x["factor"] == clave]
        lista = [x for x in lista if self.info(x["otro"])]
        lista.sort(key=lambda a: (-abs(a["r"]), a["otro"]))
        return {"sig": [x for x in lista if x["sig"]][:maximo], "todos": lista[:maximo]}

    def texto_asociado(self, a) -> str:
        return (f"{self.nombre_corto(self.info(a['otro']))} (r = {_signo(a['r'], 2)} en {a['anio']}, "
                f"{'misma dirección' if a['r'] > 0 else 'dirección opuesta'})")

    def res_ayuda(self) -> Respuesta:
        cat = self.catalogo()
        sal = [c for c in cat if self.es_salud(c)]
        soc = [c for c in cat if not self.es_salud(c)]

        def rango(lst):
            return f"{min(c['anios'][0] for c in lst)}–{max(c['anios'][-1] for c in lst)}"
        pm = self.kb.get("indicadores", {}).get("pm25_siata") or {}
        an_pm = sorted((pm.get("promedio_estaciones") or {}).keys())
        cob = ""
        if sal:
            cob += (f"{len(sal)} indicadores de salud por comuna (MEData, {rango(sal)}: "
                    f"{', '.join(c['nombre'] for c in sal)})")
        if soc:
            temas = sorted({c["tema"] for c in soc})
            cob += (f"{', ' if cob else ''}{len(soc)} indicadores sociales de la Encuesta de "
                    f"Calidad de Vida ({rango(soc)}: {', '.join(temas)})")
        if an_pm:
            cob += f"{' y ' if cob else ''}PM2.5 por estación de SIATA ({an_pm[0]}–{an_pm[-1]})"
        ej = ["¿Qué comuna tiene la mayor mortalidad?", "¿Cómo está Manrique?",
              "¿Cómo evolucionó el dengue en Robledo?", "Tasa de intento de suicidio en Belén en 2018",
              "¿Qué factores se asocian a la mortalidad?", "Compara Popular y El Poblado",
              "¿Dónde hay más inseguridad alimentaria?", "¿Cómo ha cambiado el aire?",
              "¿Qué territorios priorizar?", "¿De dónde vienen los datos?"]
        return Respuesta(
            f"Puedo responder con {cob or 'los datos del KB'}, para los 21 territorios (16 comunas "
            f"y 5 corregimientos). Pregunta por un indicador, un territorio y/o un año. Ejemplos: "
            + " ".join("«" + e + "»" for e in ej),
            interpretacion=("Puedes combinar: indicador (mortalidad, dengue, desempleo…), territorio "
                            "(nombre o «comuna 10») y año. Si el año no existe, te digo el rango disponible."),
            limitaciones=("No hay datos individuales ni causas de muerte; las cifras son agregadas "
                          "por territorio."))

    def res_fuentes(self) -> Respuesta:
        f = self.kb.get("fuentes", {})
        partes = []
        for x in f.values():
            s = f"{x['nombre']} ({x['entidad']}"
            if x.get("serie"):
                s += f", {x['serie']}"
            if x.get("serie_historica"):
                s += f", serie histórica {x['serie_historica']}"
            if x.get("indicadores"):
                s += f", {x['indicadores']} indicadores"
            partes.append(s + ")")
        return Respuesta(f"El proyecto usa datos reales de: {'; '.join(partes)}.",
                         [{"indicador": "fuentes", "valor": list(f.keys()), "fuente": "pipeline"}])

    def res_hallazgo(self) -> Respuesta:
        h = self.kb.get("indicadores", {}).get("hallazgo_mortalidad", {})
        top, bajo = h.get("comuna_mayor_tasa"), h.get("comuna_menor_tasa")
        v = h.get("variacion_pct_2012_2022_comuna_top")
        if not top or not bajo:
            return self._no("El hallazgo principal no está en el KB.")
        anio = h.get("anio_referencia", 2022)
        ev = [{"indicador": "tasa de mortalidad", "valor": top["tasa"], "anio": anio,
               "territorio": top["nombre"], "fuente": F_MEDATA},
              {"indicador": "brecha vs menor tasa", "valor": f"{h.get('brecha_veces')}x", "anio": anio,
               "territorio": bajo["nombre"], "fuente": F_MEDATA}]
        if v is not None:
            ev.append({"indicador": "variación tasa 2012-2022", "valor": f"{v}%",
                       "territorio": top["nombre"], "fuente": F_MEDATA})
        return Respuesta(
            (f"Hallazgo principal: {top['nombre']} tiene la mayor tasa de mortalidad "
             f"({num(top['tasa'])} por 100.000 hab., {anio}), {num(h.get('brecha_veces'))} veces la de "
             f"{bajo['nombre']} ({num(bajo['tasa'])})"
             + (f", y aumentó {num(v)}% entre 2012 y 2022." if v is not None else ".")),
            ev,
            "La brecha territorial es grande y persistente: el lugar de residencia se asocia con la carga de mortalidad.",
            ("Priorizar intervenciones intersectoriales en los territorios de mayor índice de "
             "priorización y monitorear su evolución."),
            "Tasas brutas, sin estandarizar por edad. Asociación, no causalidad.")

    def res_priorizacion(self) -> Respuesta:
        idx = self.kb.get("indicadores", {}).get("indice_priorizacion")
        if not idx or not idx.get("ranking"):
            r = self.ranking_mort()
            if not r:
                return self._no("El indicador de mortalidad no está en el KB.")
            top3 = r[:3]
            return Respuesta(
                (f"Con criterio de mortalidad 2022, los tres territorios a priorizar serían: "
                 f"{', '.join(x['nombre'] for x in top3)}."),
                [{"indicador": "tasa de mortalidad", "valor": x["tasa"], "anio": 2022,
                  "territorio": x["nombre"], "fuente": F_MEDATA} for x in top3],
                "Son los de mayor tasa de mortalidad del período.",
                "Distribuir intervenciones según necesidad y definir indicadores para evaluar resultados.",
                "Priorización por un solo indicador; un índice multivariable (social+ambiental) sería más robusto.")
        top3 = idx["ranking"][:3]
        comps = " + ".join(idx.get("componentes", []))
        return Respuesta(
            (f"Según el índice multivariable de priorización en salud ({comps}, normalizados 0-100), "
             f"los tres territorios a priorizar son: {', '.join(x['nombre'] for x in top3)} "
             f"(índice: {', '.join(num(x['indice']) for x in top3)})."),
            [{"indicador": "índice de priorización", "valor": x["indice"], "anio": idx.get("anio"),
              "territorio": x["nombre"], "fuente": idx.get("fuente", "MEData")} for x in top3],
            ("El índice combina dos dimensiones de salud por comuna (mortalidad y salud mental), "
             "cada una normalizada; un valor alto refleja prioridad en más de un indicador, no en uno solo."),
            ("Concentrar intervenciones intersectoriales en los territorios de mayor índice y "
             "monitorear ambos componentes."),
            ("El índice combina solo indicadores de salud medidos por comuna (MEData). El PM2.5 "
             "(SIATA) es por estación y se reporta como contexto ambiental aparte, no dentro del "
             "índice. Asociación, no causalidad."))

    def res_ambiental(self, anios: list, tendencia: bool) -> Respuesta:
        pm = self.kb.get("indicadores", {}).get("pm25_siata")
        if not pm or not pm.get("ranking"):
            return self._no("Aún no hay datos de PM2.5 (SIATA) en el knowledge base. "
                            "Ejecuta el pipeline para incorporarlos.")
        lim = (pm.get("advertencia", "") + " Además, una asociación con la salud no implica "
               "causalidad sin un diseño de estudio adecuado.")
        prom = pm.get("promedio_estaciones") or {}
        ap = sorted(prom)
        if (tendencia or len(anios) >= 2) and len(ap) >= 2:
            ini, fin = ap[0], ap[-1]
            if len(anios) >= 2:
                a, b = str(min(anios)), str(max(anios))
                if a in prom:
                    ini = a
                if b in prom:
                    fin = b
            sel = [a for a in ap if ini <= a <= fin]
            v0, v1 = prom[ini], prom[fin]
            pct = (v1 / v0 - 1) * 100
            return Respuesta(
                (f"El promedio anual de PM2.5 de las estaciones SIATA pasó de {num(v0)} µg/m³ en {ini} "
                 f"a {num(v1)} µg/m³ en {fin} ({_signo(pct, 1)}%). La guía de la OMS es 5 µg/m³: "
                 f"en {fin} el promedio la supera {_fx(v1 / 5, 1)} veces."),
                [{"indicador": "PM2.5 promedio de estaciones", "valor": prom[a], "anio": int(a),
                  "territorio": "estaciones SIATA", "fuente": "SIATA"} for a in sel],
                ("La tendencia resume el promedio simple de las estaciones con datos válidos cada "
                 "año (años completos)."),
                "Sostener las medidas que reducen el PM2.5 y vigilar las estaciones que empeoran.",
                lim + " " + pm.get("criterio", ""))
        nota, ranking, anio = "", pm["ranking"], pm["anio"]
        if anios:
            pedido, serie = anios[0], pm.get("serie") or {}
            disp = sorted({a for x in serie.values() for a in x})
            if str(pedido) in disp:
                anio = pedido
                ranking = sorted(({"estacion": e, "media_pm25": serie[e][str(pedido)]}
                                  for e in serie if str(pedido) in serie[e]),
                                 key=lambda x: (-x["media_pm25"], x["estacion"]))
            elif pedido != pm["anio"]:
                nota = (f"PM2.5 tiene medias anuales válidas para {', '.join(disp)}; no para "
                        f"{pedido}. Muestro {pm['anio']}. ")
        top = ranking[0]
        pa = prom.get(str(anio))
        return Respuesta(
            (f"{nota}En {anio}, la estación con mayor PM2.5 promedio fue {top['estacion']} con "
             f"{num(top['media_pm25'])} µg/m³. La medición de calidad del aire es por estación de monitoreo."
             + (f" Promedio de estaciones: {num(pa)} µg/m³ (guía OMS: 5)." if pa is not None else "")),
            [{"indicador": "PM2.5 media anual", "valor": x["media_pm25"], "anio": anio,
              "territorio": "estación " + x["estacion"], "fuente": "SIATA"} for x in ranking[:5]],
            ("Mayor PM2.5 implica peor calidad del aire en el entorno de esa estación; la exposición "
             "puede asociarse a afecciones respiratorias."),
            "Reforzar seguimiento y medidas preventivas en los periodos y zonas con mayor PM2.5.",
            lim)

    def res_factores(self, clave, causa: bool) -> Respuesta:
        c = self.info(clave)
        asoc = self.asociados(clave, 5)
        if not c or not asoc["todos"]:
            return self._no("No hay correlaciones calculadas para ese indicador en el KB.")
        lista = asoc["sig"] if asoc["sig"] else asoc["todos"][:3]
        intro = ((SIN_CAUSA if clave == "mortalidad" else SIN_CAUSA_GEN)
                 + "Lo que sí muestran los datos: ") if causa else ""
        items = "; ".join(self.texto_asociado(a) for a in lista)
        if asoc["sig"]:
            cuerpo = (f"entre los 21 territorios, la {self.etiqueta(c)} se asocia de forma "
                      f"estadísticamente apreciable con: {items}.")
        else:
            cuerpo = (f"entre los 21 territorios, ninguna correlación con la {self.etiqueta(c)} "
                      f"supera el umbral aproximado del 95%; las más altas son: {items}.")
        return Respuesta(
            intro + _capital(cuerpo),
            [{"indicador": "correlación con " + c["nombre"] + ": " + self.info(a["otro"])["nombre"],
              "valor": _signo(a["r"], 2), "anio": a["anio"], "territorio": f"{a['n']} territorios",
              "fuente": "cálculo propio (MEData + ECV)"} for a in lista],
            (self._s() or {}).get("nota_correlaciones", ""),
            REC_CAUSAS,
            ("Correlación de Pearson (confirmada con Spearman) en el año más reciente común a ambos "
             "indicadores. Asociación, no causalidad."))

    def res_ranking(self, clave, anios: list, abajo: bool) -> Respuesta:
        c = self.info(clave)
        if not c:
            return self._no("El indicador no está en el KB.")
        anio, nota = self.resolver_anio(c, anios[0] if anios else None)
        vals = self.valores_anio(clave, anio)
        if not vals:
            return self._no("No hay datos de ese indicador para ese año.")
        sel = list(reversed(vals)) if abajo else vals
        t = sel[0]
        cs = f" ({t['casos']} casos)" if t["casos"] is not None else ""
        sig = " y ".join(f"{x['nombre']} ({num(x['valor'])})" for x in sel[1:3])
        ciu = (self.datos(clave) or {}).get("ciudad", {}).get(str(anio))
        txt = (f"{nota}En {anio}, el territorio con {'menor' if abajo else 'mayor'} {self.etiqueta(c)} "
               f"fue {t['nombre']} con {num(t['valor'])} {c['unidad']}{cs}.")
        if sig:
            txt += f" Le siguen {sig}."
        if ciu is not None:
            txt += f" Medellín: {num(ciu)}."
        salud = self.es_salud(c)
        return Respuesta(
            txt,
            [{"indicador": c["nombre"], "valor": x["valor"], "anio": anio, "territorio": x["nombre"],
              "fuente": self.fuente_de(c)} for x in sel[:5]],
            ("Una tasa alta indica mayor carga relativa a la población del territorio; conviene "
             "priorizar seguimiento allí.") if salud else
            "Un valor alto no siempre es negativo: depende de lo que mida el indicador.",
            (f"Priorizar programas de promoción y prevención en {t['nombre']}, con indicadores de "
             f"seguimiento.") if salud else "",
            self.limitacion(c))

    def res_tendencia(self, clave, cods: list, anios: list) -> Respuesta:
        c, d = self.info(clave), self.datos(clave)
        if not c or not d:
            return self._no("No hay serie temporal suficiente en el KB.")
        ini, fin, nota = c["anios"][0], c["anios"][-1], ""
        if len(anios) >= 2:
            ini, na = self.resolver_anio(c, min(anios))
            fin, nb = self.resolver_anio(c, max(anios))
            nota = na + nb
        rango = [a for a in c["anios"] if ini <= a <= fin]
        h = self.kb.get("indicadores", {}).get("hallazgo_mortalidad", {})
        compat = (clave == "mortalidad" and not cods and ini == c["anios"][0]
                  and fin == c["anios"][-1] and h.get("variacion_pct_2012_2022_comuna_top") is not None)
        quien = []
        if cods:
            quien += [{"nombre": self.nombre_terr(k), "serie": d["valores"].get(k, {})} for k in cods]
        elif compat:
            top = h["comuna_mayor_tasa"]
            quien.append({"nombre": top["nombre"], "serie": d["valores"].get(str(top["comuna"]), {})})
        if not cods and d.get("ciudad"):
            quien.append({"nombre": "Medellín (21 territorios)", "serie": d["ciudad"]})
        if not quien:
            v = self.valores_anio(clave, fin)
            if v:
                quien.append({"nombre": v[0]["nombre"], "serie": d["valores"][v[0]["cod"]]})
        frases, ev = [], []
        for q in quien:
            an = [a for a in rango if str(a) in q["serie"]]
            if len(an) < 2:
                continue
            s = q["serie"]
            a0, a1 = an[0], an[-1]
            v0, v1 = s[str(a0)], s[str(a1)]
            mx = mn = an[0]
            for a in an:
                if s[str(a)] > s[str(mx)]:
                    mx = a
                if s[str(a)] < s[str(mn)]:
                    mn = a
            f = f"{q['nombre']}: la {self.etiqueta(c)} pasó de {num(v0)} en {a0} a {num(v1)} en {a1}"
            if v0:
                f += f" ({_signo((v1 / v0 - 1) * 100, 1)}%)"
            f += f"; máximo {num(s[str(mx)])} en {mx} y mínimo {num(s[str(mn)])} en {mn}."
            frases.append(f)
            ev.append({"indicador": f"{c['nombre']} {a0}", "valor": v0, "anio": a0,
                       "territorio": q["nombre"], "fuente": self.fuente_de(c)})
            ev.append({"indicador": f"{c['nombre']} {a1}", "valor": v1, "anio": a1,
                       "territorio": q["nombre"], "fuente": self.fuente_de(c)})
        if not frases:
            return self._no("No hay serie temporal suficiente en el KB.")
        txt = nota
        if compat:
            v = h["variacion_pct_2012_2022_comuna_top"]
            txt += (f"Entre 2012 y 2022, la tasa de mortalidad de {h['comuna_mayor_tasa']['nombre']} "
                    f"{'aumentó' if v >= 0 else 'disminuyó'} {num(abs(v))}%. ")
        txt += " ".join(frases)
        covid = 2020 in rango and 2021 in rango and self.es_salud(c)
        return Respuesta(
            txt, ev,
            ("Los años 2020–2021 coinciden con la pandemia de COVID-19, que alteró la mortalidad y "
             "la notificación de eventos.") if covid else "",
            "",
            "Un cambio de tasa no explica sus causas por sí solo. " + self.limitacion(c))

    def res_territorio(self, cods: list, clave, anios: list, causa: bool) -> Respuesta:
        c = self.info(clave)
        if not c:
            return self._no("El indicador no está en el KB.")
        anio, nota = self.resolver_anio(c, anios[0] if anios else None)
        vals = self.valores_anio(clave, anio)
        if not vals:
            return self._no("No hay datos de ese indicador para ese año.")
        med = _mediana([x["valor"] for x in vals])
        d = self.datos(clave)
        idx = self.kb.get("indicadores", {}).get("indice_priorizacion") or {}
        ind = idx.get("ranking", [])
        frases, ev = [], []
        for k in cods:
            i = next((n for n, x in enumerate(vals) if x["cod"] == k), -1)
            nom = self.nombre_terr(k)
            if i < 0:
                frases.append(f"{nom}: sin dato de {c['nombre']} en {anio}.")
                continue
            t = vals[i]
            cs = f" ({t['casos']} casos)" if t["casos"] is not None else ""
            razon = _fx(t["valor"] / med, 2) if med else "–"
            f = (f"{nom}: {self.etiqueta(c)} {anio} de {num(t['valor'])} {c['unidad']}{cs}, puesto "
                 f"{i + 1} de {len(vals)} (1 = valor más alto), {razon} veces la mediana de los "
                 f"territorios ({_fx(med, 1)})")
            j = next((n for n, x in enumerate(ind) if str(x["comuna"]) == k), -1)
            con_indice = clave == "mortalidad" and j >= 0 and anio == idx.get("anio")
            if con_indice:
                f += (f". Índice de priorización {num(ind[j]['indice'])} (puesto {j + 1} de {len(ind)}); "
                      f"intento de suicidio {num(ind[j]['tasa_suicidio'])} por 100.000")
            serie = d["valores"].get(k, {})
            a0 = next((a for a in c["anios"] if str(a) in serie), None)
            if a0 is not None and a0 < anio and serie[str(a0)]:
                pct = (t["valor"] / serie[str(a0)] - 1) * 100
                f += f". Entre {a0} y {anio} {'aumentó' if pct >= 0 else 'disminuyó'} {_fx(abs(pct), 1)}%"
            frases.append(f + ".")
            ev.append({"indicador": c["nombre"], "valor": t["valor"], "anio": anio,
                       "territorio": nom, "fuente": self.fuente_de(c)})
            if con_indice:
                ev.append({"indicador": "índice de priorización", "valor": ind[j]["indice"],
                           "anio": anio, "territorio": nom, "fuente": F_MEDATA})
        ciu = d.get("ciudad", {}).get(str(anio))
        txt = nota + ((SIN_CAUSA if clave == "mortalidad" else SIN_CAUSA_GEN)
                      + "Lo que sí muestran los datos: " if causa else "") + " ".join(frases)
        if ciu is not None:
            txt += f" Medellín: {num(ciu)}."
        r = Respuesta(txt, ev,
                      "La posición y la razón frente a la mediana permiten ubicar al territorio dentro de la ciudad.",
                      "", self.limitacion(c))
        if causa:
            asoc = self.asociados(clave, 3)
            interp = "Una tasa alta describe cuánto ocurre, no por qué. "
            if asoc["sig"]:
                interp += ("Factores asociados entre territorios (correlación, no causalidad): "
                           + "; ".join(self.texto_asociado(a) for a in asoc["sig"]) + ". ")
            interp += ("Hipótesis a verificar, no demostradas con estos datos: estructura de edad de "
                       "la población, condiciones sociales del territorio y salud mental.")
            r.interpretacion = interp
            r.recomendacion = REC_CAUSAS
        return r

    # ── Punto de entrada ───────────────────────────────────────────
    def responder(self, pregunta: str, forzado: dict | None = None) -> Respuesta:
        """forzado (opcional): interpretación ya hecha por la IA
        {intencion, indicador, territorios[nombres], anios[], causa}."""
        if not self.kb:
            return Respuesta("No hay knowledge base disponible. Ejecuta el pipeline "
                             "(07_construir_kb.py) para generarlo.", encontrado=False)
        qn = _norm(pregunta)
        if forzado:
            intent = forzado.get("intencion") or "desconocida"
            if intent in ("fuera_de_alcance", "territorio"):
                intent = "desconocida"
            ind = forzado.get("indicador")
            clave = ind if ind and (ind == "pm25" or self.info(ind)) else None
            nombres = [_norm(n) for n in forzado.get("territorios") or []]
            cods = [t["cod"] for t in self.territorios() if _norm(t["nombre"]) in nombres][:2]
            anios = [a for a in forzado.get("anios") or []
                     if isinstance(a, int) and not isinstance(a, bool) and 1990 <= a <= 2100][:2]
            causa = bool(forzado.get("causa"))
        else:
            intent = detectar_intencion(pregunta)
            clave = self.detectar_indicador(pregunta)
            cods = self.territorios_en(pregunta)
            anios = detectar_anios(pregunta)
            causa = pide_causa(pregunta)
        if intent == "ambiental":
            clave = "pm25"

        if intent == "ayuda":
            return self.res_ayuda()
        if intent == "hallazgo":
            return self.res_hallazgo()
        if intent == "fuentes":
            return self.res_fuentes()
        if clave == "pm25":
            return self.res_ambiental(anios, intent == "tendencia" or _tiene(qn, KW_TENDENCIA))
        if not self.catalogo():
            return self._no("El knowledge base no tiene series por indicador. Ejecuta el pipeline.")
        if intent == "factores" and cods:
            return self.res_territorio(cods, clave or "mortalidad", anios, True)
        if intent == "factores" or (causa and not cods):
            return self.res_factores(clave or "mortalidad", causa)
        if intent == "priorizacion" and not cods:
            return self.res_priorizacion()
        if intent == "tendencia" or (len(anios) >= 2 and intent not in ("ranking_top", "ranking_bottom")):
            return self.res_tendencia(clave or "mortalidad", cods, anios)
        if cods:
            return self.res_territorio(cods, clave or "mortalidad", anios, causa)
        if intent in ("ranking_top", "ranking_bottom"):
            return self.res_ranking(clave or "mortalidad", anios, intent == "ranking_bottom")
        if clave:
            return self.res_ranking(clave, anios, False)
        if anios:
            return self.res_ranking("mortalidad", anios, False)
        r0 = self.ranking_mort()
        t0 = r0[0]["nombre"] if r0 else "La Candelaria"
        return self._no(
            "No identifiqué una consulta que pueda responder con los datos disponibles. Escribe "
            "«¿Qué preguntas puedo hacer?» para ver ejemplos, o prueba con: «¿Qué sabemos de la "
            f"mortalidad en {t0}?», «¿Qué comunas priorizar?», «¿Cómo evolucionó el dengue?» o "
            "«¿Qué relación hay entre el aire y la salud?».")


if __name__ == "__main__":
    import sys
    m = MotorAsistente()
    pregunta = " ".join(sys.argv[1:]) or "¿Qué preguntas puedo hacer?"
    print(json.dumps(m.responder(pregunta).to_dict(), indent=2, ensure_ascii=False))
