#!/usr/bin/env python3
"""
asistente/motor.py — Motor determinista del asistente (fase 2).

Interpreta preguntas en lenguaje natural mediante reglas e intenciones y
responde SOLO con cifras del knowledge base generado por el pipeline.
NO usa IA ni requiere conexión: funciona siempre, incluso sin API key.

Contrato de respuesta (dataclass Respuesta):
  - respuesta_directa : str
  - evidencia         : list[dict]  (indicador, valor, anio, territorio, fuente)
  - interpretacion    : str
  - recomendacion     : str
  - limitaciones      : str
  - encontrado        : bool
"""
from __future__ import annotations
import json
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
KB_PATH = BASE / "outputs" / "kb" / "knowledge_base.json"


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


def _norm(texto: str) -> str:
    """Minúsculas sin acentos, para comparar de forma robusta."""
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


SIN_CAUSA = ("Los datos del proyecto no incluyen la causa específica de las "
             "defunciones (no hay desagregación por causa ni por edad), por lo "
             "que no puedo afirmar qué las causa. ")


def _aliases(nombre: str) -> list:
    """Variantes del nombre de un territorio (igual que aliasesTerritorio en JS)."""
    n = _norm(nombre)
    sin_art = re.sub(r"^(la|el|los|las) ", "", n)
    sin_corr = re.sub(r"^corregimiento de ", "", sin_art)
    out = {n, sin_art, sin_corr, re.sub(r"^san sebastian de ", "", sin_corr)}
    if "laureles" in n:
        out |= {"laureles", "estadio"}
    return [a for a in out if len(a) >= 4]


def _pide_causa(q: str) -> bool:
    qn = _norm(q)
    return any(w in qn for w in ["causa", "por que", "porque", "motivo", "razon",
                                 "explica", "factor", "se debe", "origen"])


def _mediana(vals: list) -> float:
    v = sorted(vals)
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


class MotorAsistente:
    def __init__(self, kb_path: Path = KB_PATH):
        self.kb_path = kb_path
        self.kb = self._cargar()

    def _cargar(self) -> dict:
        if not self.kb_path.exists():
            return {}
        return json.loads(self.kb_path.read_text(encoding="utf-8"))

    # ── Detección de intención ─────────────────────────────
    def _intencion(self, q: str) -> str:
        qn = _norm(q)
        # El orden importa: intenciones específicas antes que las genéricas.
        if any(w in qn for w in ["hallazgo", "conclusion principal",
                                 "resultado principal", "descubrimiento"]):
            return "hallazgo"
        if any(w in qn for w in ["aire", "contaminacion", "pm2.5", "pm25",
                                 "pm 2.5", "particulas", "ambiental",
                                 "calidad del aire", "polucion", "siata", "respirar"]):
            return "ambiental"
        if any(w in qn for w in ["tres territorios", "3 territorios", "presupuesto",
                                 "intervenir", "invertir", "priorizar", "priorizacion"]):
            return "priorizacion"
        if any(w in qn for w in ["evolucion", "tendencia", "vario", "cambio",
                                 "aumento", "disminuyo", "entre 2012", "historico",
                                 "mejorado", "2012 y"]):
            return "tendencia"
        if any(w in qn for w in ["fuente", "de donde", "datos reales"]):
            return "fuentes"
        if any(w in qn for w in ["menor", "mas baja", "mejor"]):
            return "ranking_bottom"
        if any(w in qn for w in ["mayor", "mas alta", "peor", "atencion",
                                 "mayores necesidades", "cuales comunas",
                                 "mortalidad", "defunciones", "muertes"]):
            return "ranking_top"
        return "desconocida"

    # ── Acceso a datos del KB ──────────────────────────────
    def _ranking(self) -> list:
        return (self.kb.get("indicadores", {})
                       .get("mortalidad_2022", {})
                       .get("ranking", []))

    def _territorios_en(self, q: str) -> list:
        """Índices (en el ranking) de hasta 2 territorios mencionados en la pregunta."""
        qn = " " + re.sub(r" +", " ", re.sub(r"[^a-z0-9 ]", " ", _norm(q))) + " "
        hallados = []
        for i, t in enumerate(self._ranking()):
            mejor = max((len(a) for a in _aliases(t["nombre"])
                         if f" {a} " in qn), default=0)
            if mejor:
                hallados.append((i, mejor))
        hallados.sort(key=lambda x: -x[1])
        return sorted(i for i, _ in hallados[:2])

    def _resp_territorio(self, idxs: list, causa: bool) -> Respuesta:
        r = self._ranking()
        med = _mediana([x["tasa"] for x in r])
        ind = (self.kb.get("indicadores", {}).get("indice_priorizacion") or {}).get("ranking", [])
        h = self.kb.get("indicadores", {}).get("hallazgo_mortalidad", {})
        var = h.get("variacion_pct_2012_2022_comuna_top")
        frases, ev = [], []
        for i in idxs:
            t = r[i]
            f = (f"{t['nombre']}: tasa de mortalidad general 2022 de {t['tasa']} por "
                 f"100.000 hab. ({t['casos']} defunciones), puesto {i + 1} de {len(r)} "
                 f"(1 = mayor tasa), {t['tasa'] / med:.2f} veces la mediana de los "
                 f"territorios ({med:.1f})")
            j = next((k for k, x in enumerate(ind) if x["comuna"] == t["comuna"]), -1)
            if j >= 0:
                f += (f". Índice de priorización {ind[j]['indice']:g} (puesto {j + 1} de "
                      f"{len(ind)}); intento de suicidio {ind[j]['tasa_suicidio']:g} por 100.000")
            if h.get("comuna_mayor_tasa", {}).get("comuna") == t["comuna"] and var is not None:
                f += (f". Su tasa {'aumentó' if var >= 0 else 'disminuyó'} "
                      f"{abs(var):g}% entre 2012 y 2022")
            frases.append(f + ".")
            ev.append({"indicador": "tasa de mortalidad", "valor": t["tasa"], "anio": 2022,
                       "territorio": t["nombre"], "fuente": "MEData - Secretaría de Salud"})
            if j >= 0:
                ev.append({"indicador": "índice de priorización", "valor": ind[j]["indice"],
                           "anio": 2022, "territorio": t["nombre"],
                           "fuente": "MEData - Secretaría de Salud"})
        directa = (SIN_CAUSA + "Lo que sí muestran los datos: " if causa else "") + " ".join(frases)
        if causa:
            interp = ("Una tasa alta describe cuánto se muere, no por qué. Posibles factores "
                      "a verificar (hipótesis, no demostradas con estos datos): estructura de "
                      "edad de la población, condiciones sociales del territorio y salud mental "
                      "(el índice incluye intento de suicidio).")
            rec = ("Para identificar causas: pedir a MEData/Secretaría de Salud las defunciones "
                   "por causa (CIE-10) y grupo de edad por comuna, y estandarizar las tasas por edad.")
        else:
            interp = "La posición y la razón frente a la mediana permiten ubicar al territorio dentro de la ciudad."
            rec = ""
        return Respuesta(directa, ev, interp, rec,
                         "Tasas brutas, sin estandarizar por edad; asociación, no causalidad.")

    # ── Respuestas por intención ───────────────────────────
    def responder(self, pregunta: str) -> Respuesta:
        if not self.kb:
            return Respuesta(
                "No hay knowledge base disponible. Ejecuta el pipeline "
                "(07_construir_kb.py) para generarlo.", encontrado=False)

        intent = self._intencion(pregunta)
        ranking = self._ranking()
        if not ranking and intent in ("ranking_top", "ranking_bottom",
                                      "tendencia", "priorizacion"):
            return Respuesta("El indicador de mortalidad no está en el KB.",
                             encontrado=False)

        causa = _pide_causa(pregunta)
        idxs = [] if intent in ("hallazgo", "ambiental", "fuentes") else self._territorios_en(pregunta)
        if idxs and ranking:
            return self._resp_territorio(idxs, causa)
        if causa and intent == "desconocida" and ranking:
            t, b = ranking[0], ranking[-1]
            return Respuesta(
                SIN_CAUSA + f"Lo que sí muestran: la mayor tasa 2022 está en {t['nombre']} "
                f"({t['tasa']} por 100.000 hab.) y la menor en {b['nombre']} ({b['tasa']}). "
                f"Pregunta por un territorio concreto, p. ej. «¿Qué sabemos de mortalidad en {t['nombre']}?».",
                [{"indicador": "tasa de mortalidad", "valor": t["tasa"], "anio": 2022,
                  "territorio": t["nombre"], "fuente": "MEData - Secretaría de Salud"}],
                "El análisis es descriptivo y territorial: identifica dónde se concentra la mortalidad, no su causa.",
                "Pedir defunciones por causa (CIE-10) y edad para un análisis causal o estandarizado.",
                "Asociación, no causalidad.")

        if intent == "ranking_top":
            top = ranking[0]
            ev = [{"indicador": "tasa de mortalidad", "valor": top["tasa"],
                   "anio": 2022, "territorio": top["nombre"],
                   "fuente": "MEData - Secretaría de Salud"}]
            return Respuesta(
                respuesta_directa=(
                    f"La comuna con mayor tasa de mortalidad en 2022 fue "
                    f"{top['nombre']} con {top['tasa']} defunciones por "
                    f"100.000 habitantes ({top['casos']} casos)."),
                evidencia=ev,
                interpretacion=(
                    "Una tasa alta indica mayor carga de mortalidad relativa a "
                    "su población; conviene priorizar seguimiento en este territorio."),
                recomendacion=(
                    f"Priorizar programas de promoción y prevención en "
                    f"{top['nombre']}, con indicadores de seguimiento."),
                limitaciones=(
                    "La tasa de mortalidad general depende de la estructura de "
                    "edad de la comuna; es asociación, no causalidad."))

        if intent == "ranking_bottom":
            bot = ranking[-1]
            ev = [{"indicador": "tasa de mortalidad", "valor": bot["tasa"],
                   "anio": 2022, "territorio": bot["nombre"],
                   "fuente": "MEData - Secretaría de Salud"}]
            return Respuesta(
                respuesta_directa=(
                    f"El territorio con menor tasa de mortalidad en 2022 fue "
                    f"{bot['nombre']} con {bot['tasa']} por 100.000 hab."),
                evidencia=ev,
                limitaciones="Asociación, no causalidad; influye la estructura de edad.")

        if intent == "priorizacion":
            idx = self.kb.get("indicadores", {}).get("indice_priorizacion")
            if idx and idx.get("ranking"):
                top3 = idx["ranking"][:3]
                comps = " + ".join(idx.get("componentes", []))
                nombres = ", ".join(r["nombre"] for r in top3)
                return Respuesta(
                    respuesta_directa=(
                        f"Según el índice multivariable de priorización en salud "
                        f"({comps}, normalizados 0-100), los tres territorios a "
                        f"priorizar son: {nombres} "
                        f"(índice: {', '.join(str(r['indice']) for r in top3)})."),
                    evidencia=[{"indicador": "índice de priorización",
                                "valor": r["indice"], "anio": idx.get("anio"),
                                "territorio": r["nombre"],
                                "fuente": idx.get("fuente", "MEData")} for r in top3],
                    interpretacion=(
                        "El índice combina dos dimensiones de salud por comuna "
                        "(mortalidad y salud mental), cada una normalizada; un valor "
                        "alto refleja prioridad en más de un indicador, no en uno solo."),
                    recomendacion=("Concentrar intervenciones intersectoriales en los "
                                   "territorios de mayor índice y monitorear ambos "
                                   "componentes."),
                    limitaciones=(
                        "El índice combina solo indicadores de salud medidos por "
                        "comuna (MEData). El PM2.5 (SIATA) es por estación y se "
                        "reporta como contexto ambiental aparte, no dentro del índice. "
                        "Asociación, no causalidad."))
            # Fallback: priorización por mortalidad si no hay índice.
            top3 = ranking[:3]
            ev = [{"indicador": "tasa de mortalidad", "valor": r["tasa"],
                   "anio": 2022, "territorio": r["nombre"],
                   "fuente": "MEData - Secretaría de Salud"} for r in top3]
            nombres = ", ".join(r["nombre"] for r in top3)
            return Respuesta(
                respuesta_directa=(
                    f"Con criterio de mortalidad 2022, los tres territorios a "
                    f"priorizar serían: {nombres}."),
                evidencia=ev,
                interpretacion="Son los de mayor tasa de mortalidad del período.",
                recomendacion=("Distribuir intervenciones según necesidad y definir "
                               "indicadores para evaluar resultados."),
                limitaciones=("Priorización por un solo indicador; un índice "
                              "multivariable (social+ambiental) sería más robusto."))

        if intent == "tendencia":
            h = self.kb.get("indicadores", {}).get("hallazgo_mortalidad", {})
            var = h.get("variacion_pct_2012_2022_comuna_top")
            top = h.get("comuna_mayor_tasa", {})
            if var is None:
                return Respuesta("No hay serie temporal suficiente en el KB.",
                                 encontrado=False)
            signo = "aumentó" if var >= 0 else "disminuyó"
            return Respuesta(
                respuesta_directa=(
                    f"Entre 2012 y 2022, la tasa de mortalidad de "
                    f"{top.get('nombre','la comuna top')} {signo} {abs(var)}%."),
                evidencia=[{"indicador": "variación tasa mortalidad 2012-2022",
                            "valor": f"{var}%", "territorio": top.get("nombre"),
                            "fuente": "MEData - Secretaría de Salud"}],
                limitaciones="Un cambio de tasa no explica sus causas por sí solo.")

        if intent == "ambiental":
            pm = self.kb.get("indicadores", {}).get("pm25_siata")
            if not pm or not pm.get("ranking"):
                return Respuesta(
                    "Aún no hay datos de PM2.5 (SIATA) en el knowledge base. "
                    "Ejecuta el pipeline para incorporarlos.", encontrado=False)
            top = pm["ranking"][0]
            return Respuesta(
                respuesta_directa=(
                    f"En {pm['anio']}, la estación con mayor PM2.5 promedio fue "
                    f"{top['estacion']} con {top['media_pm25']} µg/m³. "
                    f"La medición de calidad del aire es por estación de monitoreo."),
                evidencia=[{"indicador": "PM2.5 media anual",
                            "valor": e["media_pm25"], "anio": pm["anio"],
                            "territorio": "estación " + e["estacion"],
                            "fuente": "SIATA"} for e in pm["ranking"][:5]],
                interpretacion=("Mayor PM2.5 implica peor calidad del aire en el "
                                "entorno de esa estación; puede asociarse a "
                                "afecciones respiratorias."),
                recomendacion=("Reforzar seguimiento y medidas preventivas en los "
                               "periodos y zonas con mayor PM2.5."),
                limitaciones=(pm.get("advertencia", "") + " Una asociación con la "
                              "salud no implica causalidad sin un diseño adecuado."))

        if intent == "hallazgo":
            h = self.kb.get("indicadores", {}).get("hallazgo_mortalidad", {})
            top, bajo = h.get("comuna_mayor_tasa"), h.get("comuna_menor_tasa")
            if not top or not bajo:
                return Respuesta("El hallazgo principal no está en el KB.",
                                 encontrado=False)
            var = h.get("variacion_pct_2012_2022_comuna_top")
            fuente = "MEData - Secretaría de Salud"
            ev = [
                {"indicador": "tasa de mortalidad", "valor": top["tasa"],
                 "anio": h.get("anio_referencia", 2022),
                 "territorio": top["nombre"], "fuente": fuente},
                {"indicador": "brecha vs menor tasa", "valor": f"{h.get('brecha_veces')}x",
                 "anio": h.get("anio_referencia", 2022),
                 "territorio": bajo["nombre"], "fuente": fuente},
            ]
            if var is not None:
                ev.append({"indicador": "variación tasa 2012-2022", "valor": f"{var}%",
                           "territorio": top["nombre"], "fuente": fuente})
            return Respuesta(
                respuesta_directa=(
                    f"Hallazgo principal: {top['nombre']} tiene la mayor tasa de "
                    f"mortalidad ({top['tasa']} por 100.000 hab., "
                    f"{h.get('anio_referencia', 2022)}), {h.get('brecha_veces')} veces la de "
                    f"{bajo['nombre']} ({bajo['tasa']})"
                    + (f", y aumentó {var}% entre 2012 y 2022." if var is not None else ".")),
                evidencia=ev,
                interpretacion=("La brecha territorial es grande y persistente: "
                                "el lugar de residencia se asocia con la carga de mortalidad."),
                recomendacion=("Priorizar intervenciones intersectoriales en los "
                               "territorios de mayor índice de priorización y monitorear su evolución."),
                limitaciones=("Tasas brutas, sin estandarizar por edad. "
                              "Asociación, no causalidad."))

        if intent == "fuentes":
            fuentes = self.kb.get("fuentes", {})
            txt = "; ".join(f"{v['nombre']} ({v['entidad']})"
                            for v in fuentes.values())
            return Respuesta(
                respuesta_directa=f"El proyecto usa datos reales de: {txt}.",
                evidencia=[{"indicador": "fuentes", "valor": list(fuentes.keys()),
                            "fuente": "pipeline"}])

        # Intención desconocida: orientar sin inventar.
        nombre0 = ranking[0]["nombre"] if ranking else "La Candelaria"
        otros = ", ".join(x["nombre"] for x in ranking[:3])
        return Respuesta(
            respuesta_directa=(
                "No identifiqué una consulta que pueda responder con los datos "
                f"disponibles. Prueba con: «¿Qué sabemos de la mortalidad en {nombre0}?», "
                "«¿Qué comunas priorizar?», «¿Cómo varió la mortalidad entre 2012 y 2022?», "
                "«¿Qué relación hay entre el aire y la salud?» o «¿De dónde vienen los datos?». "
                f"También puedes nombrar un territorio ({otros}…)."),
            encontrado=False,
            limitaciones="El asistente solo responde con cifras del pipeline.")


if __name__ == "__main__":
    import sys
    m = MotorAsistente()
    pregunta = " ".join(sys.argv[1:]) or "¿Qué comuna debería recibir mayor atención?"
    r = m.responder(pregunta)
    print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
