# Desplegar el asistente en la web (Streamlit Community Cloud)

Objetivo: que el jurado abra un **enlace** y use el asistente sin instalar nada.
Es gratis y se conecta con tu cuenta de GitHub. Toma ~5 minutos (lo haces tú,
porque requiere iniciar sesión).

## Pasos

1. Entra a **https://share.streamlit.io** e inicia sesión con tu cuenta de GitHub
   (`watabares`).
2. Clic en **"Create app"** → **"Deploy a public app from GitHub"**.
3. Completa:
   - **Repository:** `watabares/medellin-bienestar-datos`
   - **Branch:** `main`
   - **Main file path:** `asistente/app.py`
4. (Opcional) En **Advanced settings → Secrets**, si quieres activar la capa LLM:
   ```
   OPENAI_API_KEY = "tu_clave"
   ```
   Sin esto, el asistente funciona igual en modo determinista.
5. Clic en **Deploy**. Al terminar te da una URL pública tipo:
   `https://medellin-bienestar-datos.streamlit.app`

## Después del deploy

- Pega esa URL en:
  - `COMO_EJECUTAR.md` (Opción B)
  - `instrucciones.txt` (campo "PROBARLO EN LÍNEA")
- Pruébala en una ventana de incógnito para confirmar que abre sin iniciar sesión
  (lo exigen las reglas de la Hackathon).

## Nota técnica

El asistente solo necesita `streamlit` y lee el `outputs/kb/knowledge_base.json`
ya versionado en el repo. No descarga datos ni procesa archivos pesados, por eso
el despliegue es rápido y estable.
