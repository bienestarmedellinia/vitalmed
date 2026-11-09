# Cómo ejecutar — guía para el jurado

Este proyecto tiene **dos partes**:
1. Un **pipeline automático** que descarga y procesa datos oficiales (corre en
   GitHub, no hace falta instalar nada para verlo).
2. Un **observatorio web** que presenta la salud y el bienestar por territorio a
   partir de las cifras del pipeline (cálculo determinista, sin inventar datos).

Elige la opción que prefieras, de la más simple a la más técnica.

---

## Opción A · Solo mirar los resultados (0 instalación)

Todo está publicado en el repositorio y abre en el navegador:
- **Hallazgo principal y gráficos:** ver el `README.md` del repositorio.
- **Gráficos** (`outputs/graficos/`): ranking por comuna, evolución y diagrama.
- **Cifras** (`outputs/tablas/`): `hallazgo.json`, ranking completo en CSV.

No requiere Windows, ni Python, ni comandos.

---

## Opción B · Observatorio en la web (0 instalación)  ← recomendado

Abre este enlace en cualquier navegador y explora:

>  **https://bienestarmedellinia.github.io/vitalmed/**

Qué puedes hacer:
- Recorrer las **13 categorías** del observatorio; cada una abre su análisis
  técnico y sus preguntas, con gráfica, tabla y descarga CSV.
- Usar el **mapa interactivo**: colorear los 21 territorios por indicador y año,
  y ver la red de hallazgos (correlaciones significativas).
- Consultar el **explorador de datos**: https://bienestarmedellinia.github.io/vitalmed/datos.html

---

## Opción C · Motor determinista en tu computador (línea de comandos)

Requiere **Python 3.11**. No necesita instalar dependencias (el motor usa solo
la librería estándar y el knowledge base incluido en el repositorio).

1. En GitHub, botón verde **Code → Download ZIP**. Descomprime el archivo.
2. Abre una terminal en la carpeta descomprimida.
3. Ejecuta una pregunta:

```
python asistente/app.py --cli "¿Qué comunas priorizar en salud?"
```

**¿Funcionó?** Verás la respuesta "La Candelaria, Laureles Estadio, Manrique…"
con su evidencia, fuente y limitaciones. Es el mismo motor determinista que usa
el observatorio web; esta vía es solo una verificación local opcional.

---

## Opción D · Verificar el pipeline completo (técnico)

En la pestaña **Actions** del repositorio → workflow **pipeline-principal** →
**Run workflow**. Verás los 8 pasos descargar los datos oficiales, validarlos,
integrarlos, analizarlos y generar los resultados. Al terminar, descarga el
artefacto **resultados-ecv**.

**¿Funcionó?** Todos los pasos en verde y, en el paso 2, el texto
"VALIDACIÓN OK: llave territorial consistente en todas las bases".

> Nota: el pipeline descarga datos reales (~95 MB) y lee archivos grandes; por
> eso corre en los servidores de GitHub y no requiere tu computador.
