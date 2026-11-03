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

        if intent == "fuentes":
            fuentes = self.kb.get("fuentes", {})
            txt = "; ".join(f"{v['nombre']} ({v['entidad']})"
                            for v in fuentes.values())
            return Respuesta(
                respuesta_directa=f"El proyecto usa datos reales de: {txt}.",
                evidencia=[{"indicador": "fuentes", "valor": list(fuentes.keys()),
                            "fuente": "pipeline"}])

        # Intención desconocida: orientar sin inventar.
        return Respuesta(
            respuesta_directa=(
                "No identifiqué una consulta que pueda responder con los datos "
                "disponibles. Puedo responder sobre: comunas con mayor/menor "
                "mortalidad, priorización territorial, tendencia 2012-2022 y fuentes."),
            encontrado=False,
            limitaciones="El asistente solo responde con cifras del pipeline.")


if __name__ == "__main__":
    import sys
    m = MotorAsistente()
    pregunta = " ".join(sys.argv[1:]) or "¿Qué comuna debería recibir mayor atención?"
    r = m.responder(pregunta)
    print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
