#!/usr/bin/env python3
"""
asistente/llm.py — Capa LLM OPCIONAL del asistente (fase 2).

Mejora la REDACCIÓN de una respuesta que el motor determinista ya construyó
con cifras verificadas. El LLM NO genera cifras: recibe la evidencia ya
recuperada y solo la expresa en lenguaje natural más fluido.

Comportamiento clave:
  - Si NO hay API key (OPENAI_API_KEY) o falta la librería -> se omite y se
    devuelve la respuesta determinista intacta. El sistema SIEMPRE funciona.
  - El prompt prohíbe explícitamente añadir o alterar números.
"""
from __future__ import annotations
import json
import os

from motor import Respuesta


def disponible() -> bool:
    """True solo si hay API key y librería; si no, se usa el modo determinista."""
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


def redactar(pregunta: str, r: Respuesta) -> Respuesta:
    """Devuelve la respuesta con la redacción mejorada por el LLM.
    Si el LLM no está disponible o falla, devuelve r sin cambios."""
    if not disponible():
        return r
    if not r.encontrado:
        return r
    try:
        import openai
        cliente = openai.OpenAI()
        # Solo pasamos cifras YA verificadas. El LLM no debe inventar.
        contexto = {
            "pregunta": pregunta,
            "respuesta_base": r.respuesta_directa,
            "evidencia": r.evidencia,
            "interpretacion": r.interpretacion,
            "recomendacion": r.recomendacion,
            "limitaciones": r.limitaciones,
        }
        system = (
            "Eres un asistente de inteligencia territorial de salud y bienestar "
            "de Medellín. Reglas ESTRICTAS: (1) usa EXCLUSIVAMENTE las cifras del "
            "contexto; (2) NO inventes ni modifiques números, territorios ni años; "
            "(3) cita la fuente; (4) no confundas correlación con causalidad; "
            "(5) si falta información, dilo. Redacta claro para público no técnico.")
        resp = cliente.chat.completions.create(
            model=os.environ.get("ASISTENTE_MODELO", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(contexto, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
        texto = resp.choices[0].message.content.strip()
        # La redacción mejora respuesta_directa; la evidencia/limitaciones se
        # conservan tal cual (son las cifras verificadas).
        r.respuesta_directa = texto
        return r
    except Exception as e:  # noqa: BLE001
        # Ante cualquier fallo del LLM, no rompemos la demo: modo determinista.
        print(f"[llm] aviso: no se pudo usar el LLM ({e}); uso respuesta determinista.")
        return r
