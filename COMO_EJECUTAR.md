# Cómo ejecutar — guía para el jurado

Este proyecto tiene **dos partes**:

1. Un **pipeline de datos automatizado** que descarga, valida, integra y analiza
   datos oficiales de salud y bienestar de Medellín (6 fuentes). Se ejecuta
   **únicamente en GitHub Actions** (servidores de GitHub); no requiere instalar
   nada ni usar tu computador.
2. Un **portal web (observatorio)** que, como valor agregado, visualiza los
   resultados del pipeline (cálculo determinista, sin inventar datos).

No hay ejecución local: todo el cómputo corre en GitHub Actions. Elige la opción
que prefieras, de la más simple a la más técnica.

---

## Opción A · Observatorio en la web (0 instalación) ← recomendado

Abre este enlace en cualquier navegador y explora:

> **https://bienestarmedellinia.github.io/vitalmed/**

Qué puedes hacer:
- Recorrer las **13 categorías** del observatorio; cada una abre su análisis
  técnico y sus preguntas, con gráfica, tabla y descarga CSV.
- Usar el **mapa interactivo**: colorear los 21 territorios por indicador y año,
  y ver la red de hallazgos (correlaciones significativas).
- Consultar el **explorador de datos**:
  https://bienestarmedellinia.github.io/vitalmed/datos.html

El mensaje central es la **desigualdad territorial del bienestar**: la brecha de
mortalidad (La Candelaria, 4,58 veces la de Santa Elena) es uno de los ejemplos,
no el único.

---

## Opción B · Ver la automatización del pipeline (0 instalación)

El pipeline corre solo por cron (diario ~6 a.m. y mensual, hora Colombia), en
cada push a `main`, o de forma manual. Para comprobarlo:

> **https://github.com/bienestarmedellinia/vitalmed/actions/workflows/pipeline.yml**

Cada fila es una ejecución. Un **check (✓)** significa que terminó bien.

**Ver el detalle paso a paso de una ejecución** (p. ej. una fila que dice
"pipeline succeeded 7 hours ago in 3m 44s"):

1. Abre la URL anterior.
2. Clic en el primer **pipeline-principal** de la lista.
3. En la pantalla siguiente, dentro del recuadro **pipeline.yml**, clic en el
   botón **pipeline**.
4. Verás el detalle paso a paso del job, en orden: descargar → validar →
   limpiar → integrar → analizar → visualizar → fuentes SIATA/DANE/SIVIGILA/RIPS
   → construir la base de conocimiento → publicar resultados.

> Nota: GitHub muestra las horas en **UTC**; para hora local resta 5 horas
> (GMT-5, America/Bogotá).

---

## Opción C · Ver los resultados que produce el pipeline (0 instalación)

Los resultados se publican y actualizan en cada ejecución:

> **https://github.com/bienestarmedellinia/vitalmed/tree/main/outputs**

- `outputs/graficos/` — ranking por comuna, evolución y diagrama del pipeline.
- `outputs/tablas/` — `hallazgo.json`, rankings y análisis en CSV.

**¿Funcionó?** En Actions, el run `pipeline-principal` termina en verde con todos
sus pasos en ✓ (en el paso de validación aparece
"VALIDACIÓN OK: llave territorial consistente"), y en `outputs/` quedan las
tablas y gráficos actualizados.

---

Para el detalle completo de entorno, fuentes y licencias, ver **instrucciones.txt**.
