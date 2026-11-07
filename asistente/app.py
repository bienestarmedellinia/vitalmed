#!/usr/bin/env python3
"""
asistente/app.py — Interfaz de línea de comandos del asistente (fase 2).

Uso:
    python asistente/app.py --cli "¿Qué comuna priorizar?"
    python asistente/app.py "¿Qué comuna priorizar?"
    python asistente/app.py            # modo interactivo (pregunta/respuesta)

La interfaz WEB del asistente es el portal publicado
(https://bienestarmedellinia.github.io/vitalmed/), que usa el mismo motor
determinista en JavaScript. Este archivo es la vía local, sin navegador.

El asistente consulta el knowledge base del pipeline (cifras verificadas) y,
si hay API key de OpenAI, mejora la redacción con el LLM. Sin API key funciona igual.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motor import MotorAsistente  # noqa: E402
import llm  # noqa: E402


def responder(motor: MotorAsistente, pregunta: str):
    r = motor.responder(pregunta)
    r = llm.redactar(pregunta, r)   # mejora opcional; no cambia cifras
    return r


def run_cli() -> int:
    motor = MotorAsistente()
    modo_llm = "con LLM" if llm.disponible() else "determinista (sin API key)"
    print(f"Asistente Medellín Bienestar · modo {modo_llm}")
    args = [a for a in sys.argv[1:] if a != "--cli"]
    if args:
        _imprimir(responder(motor, " ".join(args)))
        return 0
    print("Escribe tu pregunta (o 'salir'):")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("salir", "exit", "quit", ""):
            break
        _imprimir(responder(motor, q))
    return 0


def _imprimir(r) -> None:
    print("\n── Respuesta ─────────────────────────────")
    print(r.respuesta_directa)
    if r.evidencia:
        print("\nEvidencia:")
        for e in r.evidencia:
            print(f"  · {e}")
    if r.interpretacion:
        print(f"\nInterpretación: {r.interpretacion}")
    if r.recomendacion:
        print(f"Recomendación: {r.recomendacion}")
    if r.limitaciones:
        print(f"Limitaciones: {r.limitaciones}")


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    sys.exit(main())
