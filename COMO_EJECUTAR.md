# Cómo ejecutar — guía para el jurado

Este proyecto tiene **dos partes**:
1. Un **pipeline automático** que descarga y procesa datos oficiales (corre en
   GitHub, no hace falta instalar nada para verlo).
2. Un **asistente** que responde preguntas sobre salud y bienestar por comuna.

Elige la opción que prefieras, de la más simple a la más técnica.

---

## Opción A · Solo mirar los resultados (0 instalación)

Todo está publicado en el repositorio y abre en el navegador:
- **Hallazgo principal y gráficos:** ver el `README.md` del repositorio.
- **Gráficos** (`outputs/graficos/`): ranking por comuna, evolución y diagrama.
- **Cifras** (`outputs/tablas/`): `hallazgo.json`, ranking completo en CSV.

No requiere Windows, ni Python, ni comandos.

---

## Opción B · Asistente en la web (0 instalación)  ← recomendado

Abre este enlace en cualquier navegador y escribe preguntas:

>  **[ PEGAR AQUÍ EL ENLACE DE STREAMLIT CLOUD ]**

Ejemplos de preguntas:
- ¿Qué comunas deberían recibir mayor atención en salud?
- Si hay presupuesto para 3 territorios, ¿cuáles priorizar?
- ¿Cómo varió la mortalidad entre 2012 y 2022?

---

## Opción C · Asistente en tu computador Windows (1 doble clic)

1. Descarga el proyecto (botón verde **Code → Download ZIP** en GitHub) y
   descomprímelo.
2. Entra a la carpeta y haz **doble clic en `EJECUTAR_ASISTENTE.bat`**.
3. La primera vez instala lo necesario y abre el asistente en tu navegador.
   - Si te dice que falta Python, instálalo desde python.org marcando
     *"Add Python to PATH"* y vuelve a dar doble clic.

No necesitas escribir comandos.

---

## Opción D · Verificar el pipeline completo (técnico)

En la pestaña **Actions** del repositorio → workflow **pipeline-ecv** →
**Run workflow**. Verás los 8 pasos descargar los datos oficiales, validarlos,
integrarlos, analizarlos y generar los resultados. Al terminar, descarga el
artefacto **resultados-ecv**.

> Nota: el pipeline descarga datos reales (~95 MB) y lee archivos grandes; por
> eso corre en los servidores de GitHub y no requiere tu computador.
