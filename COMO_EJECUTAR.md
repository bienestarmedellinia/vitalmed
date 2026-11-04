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

>  **https://watabares.github.io/medellin-bienestar-datos/**

Ejemplos de preguntas:
- ¿Qué comunas deberían recibir mayor atención en salud?
- Si hay presupuesto para 3 territorios, ¿cuáles priorizar?
- ¿Cómo varió la mortalidad entre 2012 y 2022?

---

## Opción C · Asistente en tu computador Windows (1 doble clic)

1. En GitHub, botón verde **Code → Download ZIP**. Descomprime el archivo.
2. Abre la carpeta descomprimida. Dentro verás `EJECUTAR_ASISTENTE.bat`
   junto a las carpetas `asistente` y `outputs`.
3. Haz **doble clic en `EJECUTAR_ASISTENTE.bat`**. Se abre una ventana negra
   que te guía paso a paso y abre el asistente en el navegador.

**¿Funcionó?** Si en el navegador ves el título "Pulso Medellín" y
puedes escribir una pregunta, está listo.

### Si algo falla (solución rápida)

| Lo que ves | Qué hacer |
|------------|-----------|
| "No se encontró Python" | Instala Python desde python.org y marca *"Add Python to PATH"*. Vuelve a dar doble clic. |
| Se abre la Microsoft Store | Cierra la Store. Instala Python desde python.org (no desde la Store). |
| "Falta knowledge_base.json" | Descargaste el ZIP incompleto. Vuelve a descargarlo completo. |
| "No se pudieron instalar las dependencias" | Revisa tu internet, o usa la **Opción B** (web, no instala nada). |
| La ventana negra se cierra sola | Abre `cmd`, arrastra el `.bat` dentro y pulsa Enter para ver el mensaje. |

> Si nada funciona, usa la **Opción B** (asistente web): no requiere instalar nada.

---

## Opción D · Verificar el pipeline completo (técnico)

En la pestaña **Actions** del repositorio → workflow **pipeline-ecv** →
**Run workflow**. Verás los 8 pasos descargar los datos oficiales, validarlos,
integrarlos, analizarlos y generar los resultados. Al terminar, descarga el
artefacto **resultados-ecv**.

**¿Funcionó?** Todos los pasos en verde y, en el paso 2, el texto
"VALIDACIÓN OK: llave territorial consistente en todas las bases".

> Nota: el pipeline descarga datos reales (~95 MB) y lee archivos grandes; por
> eso corre en los servidores de GitHub y no requiere tu computador.
