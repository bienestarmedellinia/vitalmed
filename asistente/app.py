#!/usr/bin/env python3
"""
asistente/app.py — Interfaz del asistente (fase 2).

Dos modos:
  1) Streamlit (interfaz web para el jurado):
        streamlit run asistente/app.py
  2) CLI de respaldo (si el entorno no levanta Streamlit):
        python asistente/app.py --cli
        python asistente/app.py "¿Qué comuna priorizar?"

El asistente consulta el knowledge base del pipeline (cifras verificadas) y,
si hay API key, mejora la redacción con el LLM. Sin API key funciona igual.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motor import MotorAsistente  # noqa: E402
import llm  # noqa: E402

PREGUNTAS_SUGERIDAS = [
    "¿Qué comunas deberían recibir mayor atención en salud y bienestar?",
    "¿Qué territorio tiene la menor tasa de mortalidad?",
    "Si hay presupuesto para intervenir solo 3 territorios, ¿cuáles?",
    "¿Cómo varió la mortalidad entre 2012 y 2022?",
    "¿De dónde provienen los datos del proyecto?",
]


def responder(motor: MotorAsistente, pregunta: str):
    r = motor.responder(pregunta)
    r = llm.redactar(pregunta, r)   # mejora opcional; no cambia cifras
    return r


def run_cli() -> int:
    motor = MotorAsistente()
    modo_llm = "con LLM" if llm.disponible() else "determinista (sin API key)"
    print(f"Asistente Medellín Bienestar · modo {modo_llm}")
    print("Escribe tu pregunta (o 'salir'):")
    args = [a for a in sys.argv[1:] if a != "--cli"]
    if args:
        _imprimir(responder(motor, " ".join(args)))
        return 0
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


def run_streamlit() -> None:
    import streamlit as st

    st.set_page_config(page_title="Medellín Bienestar AI", page_icon="🏥")
    st.title("🏥 Medellín Bienestar AI")
    st.caption("Asistente de inteligencia territorial para salud y bienestar. "
               "Responde con cifras verificadas del pipeline; no inventa datos.")

    motor = MotorAsistente()
    if not motor.kb:
        st.error("No hay knowledge base. Ejecuta el pipeline "
                 "(scripts/07_construir_kb.py) para generar outputs/kb/.")
        return

    modo = "con LLM" if llm.disponible() else "determinista (sin API key)"
    st.sidebar.info(f"Modo: **{modo}**")
    st.sidebar.write("Preguntas sugeridas:")
    for s in PREGUNTAS_SUGERIDAS:
        if st.sidebar.button(s):
            st.session_state["pregunta"] = s

    pregunta = st.text_input("Escribe tu pregunta:",
                             value=st.session_state.get("pregunta", ""))
    if pregunta:
        r = responder(motor, pregunta)
        st.subheader("Respuesta")
        st.write(r.respuesta_directa)
        if not r.encontrado:
            st.warning("Sin cifra directa para esta consulta.")
        if r.evidencia:
            st.subheader("Evidencia")
            st.table(r.evidencia)
        cols = st.columns(2)
        if r.interpretacion:
            cols[0].markdown(f"**Interpretación**\n\n{r.interpretacion}")
        if r.recomendacion:
            cols[1].markdown(f"**Recomendación**\n\n{r.recomendacion}")
        if r.limitaciones:
            st.caption(f"⚠️ Limitaciones: {r.limitaciones}")


def main() -> int:
    if "--cli" in sys.argv or (len(sys.argv) > 1 and "streamlit" not in sys.argv[0]):
        return run_cli()
    try:
        run_streamlit()
    except ModuleNotFoundError:
        print("Streamlit no está instalado; usando modo CLI.")
        return run_cli()
    return 0


if __name__ == "__main__":
    sys.exit(main())
