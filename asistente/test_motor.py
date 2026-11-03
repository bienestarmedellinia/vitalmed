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


def test_tendencia():
    r = M.responder("¿Cómo varió la mortalidad entre 2012 y 2022?")
    return _check("tendencia reporta +44.6%",
                  r.encontrado and "44.6" in r.respuesta_directa, r.respuesta_directa)


def test_fuentes():
    r = M.responder("¿De dónde salen los datos?")
    return _check("fuentes menciona las tres fuentes",
                  r.encontrado and "SIATA" in r.respuesta_directa
                  and "Calidad de Vida" in r.respuesta_directa, r.respuesta_directa)


def test_desconocida_no_inventa():
    r = M.responder("¿Cuál es el precio del dólar hoy?")
    return _check("pregunta fuera de alcance -> no encontrado, sin inventar",
                  (not r.encontrado), r.respuesta_directa)


def test_no_pii():
    """El KB no debe contener microdatos ni nombres de personas."""
    import json
    kb = json.dumps(M.kb)
    sospechosos = ["cedula", "identificacion", "nombre_persona", "telefono"]
    return _check("KB sin campos de PII",
                  not any(s in kb.lower() for s in sospechosos))


def main() -> int:
    tests = [test_ranking_top, test_ranking_bottom, test_priorizacion_3,
             test_tendencia, test_fuentes, test_desconocida_no_inventa, test_no_pii]
    if not M.kb:
        print("ERROR: no hay knowledge_base.json. Ejecuta scripts/07_construir_kb.py")
        return 1
    resultados = [t() for t in tests]
    ok = sum(resultados)
    print(f"\n{ok}/{len(resultados)} pruebas OK")
    return 0 if ok == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
