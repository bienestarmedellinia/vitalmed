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

>  **https://bienestarmedellinia.github.io/vitalmed/**

Ejemplos de preguntas:
- ¿Qué comunas deberían recibir mayor atención en salud?
- Si hay presupuesto para 3 territorios, ¿cuáles priorizar?
- ¿Cómo varió la mortalidad entre 2012 y 2022?

---

## Opción C · Asistente en tu computador (línea de comandos)

Requiere **Python 3.11**. No necesita instalar dependencias (el motor usa solo
la librería estándar y el knowledge base incluido en el repositorio).

1. En GitHub, botón verde **Code → Download ZIP**. Descomprime el archivo.
2. Abre una terminal en la carpeta descomprimida.
3. Ejecuta una pregunta:

```
python asistente/app.py --cli "¿Qué comunas priorizar en salud?"
```

**¿Funcionó?** Verás la respuesta "La Candelaria, Laureles Estadio, Manrique…"
con su evidencia, fuente y limitaciones. También funciona en modo interactivo
ejecutando `python asistente/app.py` sin argumentos.

> La interfaz **web** del asistente (Opción B) usa el mismo motor y no requiere
> instalar nada; es la vía recomendada para el jurado.

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
