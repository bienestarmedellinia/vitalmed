#!/usr/bin/env python3
"""
asistente/test_motor.py — Pruebas del motor determinista.

Verifica que el asistente responde con las cifras correctas del KB y que NO
inventa. Ejecutable sin pytest:  python asistente/test_motor.py
(y también con pytest si está instalado).

Requiere que exista outputs/kb/knowledge_base.json (lo genera 07_construir_kb.py).
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motor import MotorAsistente  # noqa: E402

M = MotorAsistente()


def _check(nombre: str, cond: bool, detalle: str = "") -> bool:
    estado = "PASS" if cond else "FAIL"
    print(f"[{estado}] {nombre}" + (f" — {detalle}" if detalle and not cond else ""))
    return cond


def test_ranking_top():
    r = M.responder("¿Qué comuna debería recibir mayor atención en salud?")
    return _check("ranking_top menciona La Candelaria y la cifra",
                  r.encontrado and "La Candelaria" in r.respuesta_directa
                  and "1325.6" in r.respuesta_directa, r.respuesta_directa)


def test_ranking_bottom():
    r = M.responder("¿Qué territorio tiene la menor mortalidad?")
    return _check("ranking_bottom menciona Santa Elena",
                  r.encontrado and "Santa Elena" in r.respuesta_directa,
                  r.respuesta_directa)


def test_priorizacion_3():
    r = M.responder("Si hay presupuesto para 3 territorios, ¿cuáles priorizar?")
    return _check("priorizacion devuelve 3 evidencias",
                  r.encontrado and len(r.evidencia) == 3, str(r.evidencia))


def test_indice_multivariable():
    """Si el KB trae el índice, la priorización debe usarlo (no solo mortalidad)."""
    idx = M.kb.get("indicadores", {}).get("indice_priorizacion")
    if not idx or not idx.get("ranking"):
        print("[SKIP] índice multivariable no está en el KB (aún)")
        return True
    r = M.responder("¿Cuáles 3 territorios priorizar con el presupuesto?")
    return _check("priorizacion usa el índice multivariable",
                  r.encontrado and "índice multivariable" in r.respuesta_directa
                  and "SIATA" in r.limitaciones, r.respuesta_directa)


def test_tendencia():
    r = M.responder("¿Cómo varió la mortalidad entre 2012 y 2022?")
    return _check("tendencia reporta +44.6%",
                  r.encontrado and "44.6" in r.respuesta_directa, r.respuesta_directa)


def test_hallazgo():
    r = M.responder("¿Cuál es el hallazgo principal?")
    return _check("hallazgo cita La Candelaria, 1325.6 y la brecha 4.58",
                  r.encontrado and "La Candelaria" in r.respuesta_directa
                  and "1325.6" in r.respuesta_directa
                  and "4.58" in r.respuesta_directa, r.respuesta_directa)


def test_fuentes():
    r = M.responder("¿De dónde salen los datos?")
    return _check("fuentes menciona las tres fuentes",
                  r.encontrado and "SIATA" in r.respuesta_directa
                  and "Calidad de Vida" in r.respuesta_directa, r.respuesta_directa)


def test_desconocida_no_inventa():
    r = M.responder("¿Cuál es el precio del dólar hoy?")
    return _check("pregunta fuera de alcance -> no encontrado, sin inventar",
                  (not r.encontrado), r.respuesta_directa)


def test_territorio_causa():
    r = M.responder("¿Cual es la causa de moratilidad en la Candelaria?")
    return _check("causa en La Candelaria: es honesto y da cifras del territorio",
                  r.encontrado and "no incluyen la causa" in r.respuesta_directa
                  and "1325.6" in r.respuesta_directa and "puesto 1 de 21" in r.respuesta_directa
                  and bool(r.recomendacion), r.respuesta_directa)


def test_territorio_simple():
    r = M.responder("¿Cómo está Santa Elena?")
    return _check("territorio por nombre (Santa Elena, puesto 21)",
                  r.encontrado and "289.47" in r.respuesta_directa
                  and "puesto 21 de 21" in r.respuesta_directa, r.respuesta_directa)


def test_comparar_dos():
    r = M.responder("comparar Manrique y Laureles")
    return _check("compara dos territorios",
                  r.encontrado and "Manrique" in r.respuesta_directa
                  and "Laureles Estadio" in r.respuesta_directa, r.respuesta_directa)


def test_ayuda():
    r = M.responder("¿Que preguntas te puedo realizar?")
    return _check("ayuda: explica qué se puede preguntar (sin 'no identifiqué')",
                  r.encontrado and "Ejemplos" in r.respuesta_directa
                  and "indicadores de salud" in r.respuesta_directa, r.respuesta_directa)


def test_territorio_anio():
    r = M.responder("mortalidad en Robledo en 2016")
    return _check("indicador + territorio + año histórico",
                  r.encontrado and "Robledo" in r.respuesta_directa and "2016" in r.respuesta_directa,
                  r.respuesta_directa)


def test_anio_fuera_de_cobertura():
    r = M.responder("mortalidad 2024")
    return _check("año sin datos: lo dice y muestra el último disponible",
                  r.encontrado and "no hay dato para 2024" in r.respuesta_directa
                  and "Muestro 2022" in r.respuesta_directa, r.respuesta_directa)


def test_otro_indicador_tendencia():
    if not M.info("dengue"):
        print("[SKIP] dengue no está en el KB (aún)")
        return True
    r = M.responder("¿Cómo evolucionó el dengue en Robledo?")
    return _check("tendencia de otro indicador en un territorio",
                  r.encontrado and "dengue" in r.respuesta_directa and "Robledo" in r.respuesta_directa,
                  r.respuesta_directa)


def test_factores():
    if not (M.kb.get("series") or {}).get("correlaciones"):
        print("[SKIP] correlaciones no están en el KB (aún)")
        return True
    r = M.responder("¿Qué factores se asocian a la mortalidad?")
    return _check("factores asociados (correlación, no causalidad)",
                  r.encontrado and "r = " in r.respuesta_directa
                  and "causalidad" in (r.interpretacion + r.limitaciones), r.respuesta_directa)


def test_forzado_ia():
    r = M.responder("¿qué tan grave está el centro?",
                    {"intencion": "territorio", "territorios": ["La Candelaria"],
                     "indicador": "mortalidad", "anios": [], "causa": False})
    return _check("interpretación de la IA (forzado) -> cifras del KB",
                  r.encontrado and "1325.6" in r.respuesta_directa, r.respuesta_directa)


PREGUNTAS_PARIDAD = [
    "¿Que preguntas te puedo realizar?", "¿Cual es la causa de moratilidad en la Candelaria?",
    "¿Cómo varió la mortalidad entre 2012 y 2022?", "mortalidad en Robledo en 2016",
    "mortalidad 2024", "¿Cómo evolucionó el dengue en Robledo?",
    "¿Qué factores se asocian a la mortalidad?", "¿Dónde hay más inseguridad alimentaria?",
    "¿Cómo ha cambiado el aire?", "PM2.5 en 2024", "desempleo en comuna 1",
    "Compara Popular y El Poblado en suicidio", "¿por qué mueren tantos?",
    "¿De dónde vienen los datos?", "¿Cuál es el precio del dólar hoy?",
    "¿qué explica la mortalidad en el centro?", "tuberculosis", "¿Cuál es el hallazgo principal?",
    "Si hay presupuesto para 3 territorios, ¿cuáles priorizar?", "¿Qué territorio tiene la menor mortalidad?",
    "violencia de género entre 2015 y 2020", "natalidad en Santa Elena 2030", "comparar Manrique y Laureles",
    ["¿qué tan grave está el centro?", {"intencion": "territorio", "territorios": ["La Candelaria"],
                                        "indicador": "mortalidad", "anios": [2019], "causa": True}],
    ["¿ha mejorado el aire?", {"intencion": "tendencia", "territorios": [], "indicador": "pm25",
                               "anios": [], "causa": False}],
]


def test_paridad_js():
    """El motor web (JS) y este motor (Python) deben responder lo mismo."""
    import json
    import shutil
    import subprocess
    if not shutil.which("node"):
        print("[SKIP] paridad JS: node no está instalado")
        return True
    js = json.loads(subprocess.run(
        ["node", str(Path(__file__).with_name("paridad_js.cjs")), str(M.kb_path)],
        input=json.dumps(PREGUNTAS_PARIDAD), capture_output=True, text=True, check=True).stdout)
    difs = []
    for p, j in zip(PREGUNTAS_PARIDAD, js):
        r = M.responder(p[0], p[1]) if isinstance(p, list) else M.responder(p)
        py = {"respuesta_directa": r.respuesta_directa, "encontrado": r.encontrado,
              "n_evidencia": len(r.evidencia)}
        if py != j:
            difs.append(f"\n   Q: {p}\n   JS: {j}\n   PY: {py}")
    return _check(f"paridad JS↔Python en {len(PREGUNTAS_PARIDAD)} preguntas", not difs, "".join(difs))


def test_no_pii():
    """El KB no debe contener microdatos ni nombres de personas."""
    import json
    kb = json.dumps(M.kb)
    sospechosos = ["cedula", "identificacion", "nombre_persona", "telefono"]
    return _check("KB sin campos de PII",
                  not any(s in kb.lower() for s in sospechosos))


def main() -> int:
    tests = [test_ranking_top, test_ranking_bottom, test_priorizacion_3,
             test_indice_multivariable,
             test_tendencia, test_hallazgo, test_fuentes, test_desconocida_no_inventa,
             test_territorio_causa, test_territorio_simple, test_comparar_dos,
             test_ayuda, test_territorio_anio, test_anio_fuera_de_cobertura,
             test_otro_indicador_tendencia, test_factores, test_forzado_ia, test_paridad_js,
             test_no_pii]
    if not M.kb:
        print("ERROR: no hay knowledge_base.json. Ejecuta scripts/07_construir_kb.py")
        return 1
    resultados = [t() for t in tests]
    ok = sum(resultados)
    print(f"\n{ok}/{len(resultados)} pruebas OK")
    return 0 if ok == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
