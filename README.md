# Medellín, Bienestar Basado en Datos

Proyecto para la **Hackathon de Datos 2026 · Institución Universitaria ITM**.
Modalidad: **Pipeline automático + Fase 2 (observatorio sobre sus resultados)**.
Temática: **Salud y bienestar**.

> *¿Cómo pueden las técnicas de análisis de datos identificar y explicar la
> influencia de los factores ambientales, sociales y territoriales sobre las
> condiciones de salud y bienestar de la población de Medellín, con el fin de
> apoyar la toma de decisiones y la formulación de intervenciones basadas en
> evidencia?*

Portal publicado: **https://bienestarmedellinia.github.io/vitalmed/**

## Qué hace

Un pipeline que, sin intervención manual, **descarga** datos oficiales de varias
fuentes, **valida** su consistencia, los **homologa**, **integra** y **analiza**
por territorio, y construye un **conocimiento base** (KB) que alimenta un portal
web (observatorio) y un explorador de datos. Se ejecuta íntegramente en
**GitHub Actions**.

```
scripts/
  sources.yml          Manifiesto de URLs oficiales
  01_descargar.py      Descarga desde las fuentes -> data/raw/
  02_limpiar.py        Homologa la llave territorial (p_006/P_007/A.7 -> territorio_cod)
  03_validar.py        Valida 16 comunas + 5 corregimientos
  04_integrar.py       Tabla agregada publicable -> outputs/tablas/
  05_analizar.py       Hallazgo, ranking, correlaciones e índice de priorización
  06_visualizar.py     Gráficos PNG
  08_siata.py          PM2.5 por estación (SIATA)
  10_dane_eevv.py      Mortalidad mensual por causa + edad (DANE)
  11_sivigila.py       Series semanales ESI-IRAG e intento de suicidio (SIVIGILA/INS)
  12_rips.py           Morbilidad anual por CIE-10 (RIPS/MinSalud)
  07_construir_kb.py   Integra todo al KB + exporta datos abiertos (docs/datos/)
  13_mapa_hero.py      Mapa SVG de los 21 territorios (GeoMedellín)
  14_foto_hero.py      Foto panorámica del banner (Wikimedia, CC BY-SA)
  09_guia_entrega.py   PDF de la ficha de entrega
.github/workflows/
  pipeline.yml         Orquesta todos los pasos en el runner
  portal.yml           Prueba de humo del portal en Chromium (Playwright)
```

## Fuentes (6)

| Fuente | Entidad | Dimensión | Indicadores | Enlace |
|--------|---------|-----------|-------------|--------|
| **MEData** (obligatoria) | Secretaría de Salud de Medellín | Sanitaria | 10 por comuna, 2008–2022 | https://medata.app.medellin.gov.co/ |
| **ECV** | Alcaldía de Medellín · Planeación | Social / territorial | 21 por territorio, 2007–2022 | https://www.medellin.gov.co/es/centro-documental/encuesta-calidad-de-vida/ |
| **SIATA** | SIATA · Valle de Aburrá | Ambiental (PM2.5) | 1 por estación, 2020–2025 | https://siata.gov.co/IDEAM/ |
| **DANE EEVV** | DANE | Mortalidad mensual por causa CIE-10 + edad | municipio | https://microdatos.dane.gov.co/ |
| **SIVIGILA** | INS | ESI-IRAG, intento de suicidio (semanal) | municipio | datos.gov.co (4hyg-wa9d) |
| **RIPS** | MinSalud | Atenciones anuales por CIE-10 | municipio | datos.gov.co (4k9h-8qiu) |

En total ~39 indicadores (31 por territorio + series de ciudad). Datos reales,
sin datos sintéticos. Detalle y licencias en la sección Transparencia del portal
y en `instrucciones.txt`.

## Privacidad

Las bases ECV son microdatos a nivel de persona. **No se versionan** en el
repositorio (ver `.gitignore`): el pipeline los descarga en tiempo de ejecución.
Solo se publican **tablas agregadas** por territorio, sin datos personales,
conforme a la Cláusula de Ética y Transparencia de la Hackathon.

## Nota de arquitectura

El desarrollo local se hace en una Raspberry Pi, que **no procesa los datos**
(leer las bases completas la satura). Todo el cómputo pesado corre en GitHub
Actions. La RPi solo edita código y hace `git push`.

## Hallazgo principal

> En 2022, **La Candelaria (comuna 10)** presentó la **mayor tasa de mortalidad
> de Medellín: 1.325,6 defunciones por 100.000 habitantes**, equivalente a
> **4,6 veces** la del territorio con menor tasa (corregimiento de Santa Elena,
> 289,5). Entre 2012 y 2022 su tasa **aumentó +44,6%**.

Fuente: MEData — Secretaría de Salud de Medellín (servicio `VC_Datos_Enfermedades`),
datos agregados por comuna, sin datos personales. Los 21 territorios oficiales
(16 comunas + 5 corregimientos); se excluye la categoría residual "Sin información".

Artefactos generados por el pipeline (en `outputs/` del repo y como artefacto de Actions):
- `outputs/tablas/hallazgo.json` — la cifra principal para la ficha de entrega.
- `outputs/tablas/analisis_mortalidad_comuna.csv` — ranking completo por comuna.
- `outputs/graficos/ranking_mortalidad_2022.png` — ranking por comuna.
- `outputs/graficos/evolucion_comuna_top.png` — serie temporal 2012–2022.
- `outputs/graficos/pipeline.png` — diagrama del funcionamiento del pipeline.

> Nota metodológica: una asociación territorial no implica causalidad. La tasa
> de mortalidad general está influida por la estructura de edad de cada comuna.

## Fase 2 — Observatorio de bienestar

Sobre los resultados del pipeline se construye un **observatorio web** que
presenta el bienestar multidimensional de Medellín **usando solo las cifras
verificadas** del knowledge base (`docs/knowledge_base.json`). No inventa datos.

- **Observatorio por preguntas** (`docs/index.html` + `docs/portal.js`): 13
  categorías temáticas; cada una abre un panel con resumen, indicadores clave
  (semáforo por tendencia), un **análisis técnico** narrativo por indicador
  (descripción, comportamiento histórico, análisis territorial, relaciones,
  metodología, hallazgos y conclusión) y 200 preguntas con su gráfica, tabla y
  descarga CSV. Todo se calcula de forma **determinista** a partir del KB; no se
  consultan modelos de lenguaje en tiempo de ejecución ni se envían datos a
  terceros al navegar.
- **Mapa interactivo**: coropleta de los 21 territorios que se repinta por
  indicador/año, y una **red de hallazgos** con las correlaciones significativas
  del KB (Pearson+Spearman 95%).
- **Explorador de datos** (`docs/datos.html`): tablas, gráficos y CSV de todos
  los indicadores por territorio y año, factores asociados y PM2.5. Archivos
  abiertos en `docs/datos/`.
- **Motor local opcional** (`asistente/motor.py`, `app.py --cli`): el mismo
  motor determinista por línea de comandos, para verificación. `llm.py` (OpenAI)
  queda apagado por defecto y solo redactaría una respuesta ya calculada; no
  genera cifras.

Uso local (opcional, sin instalar nada pesado; corre en la Raspberry Pi):

```bash
# el portal publicado no requiere instalar nada:
#   https://bienestarmedellinia.github.io/vitalmed/

# motor determinista por línea de comandos (mismo cálculo que el portal):
python asistente/app.py --cli "¿Qué comunas priorizar en salud?"

# pruebas del motor (verifican que responde con cifras reales + paridad JS/Py):
python asistente/test_motor.py
```

## Cómo ejecutarlo

Ver `instrucciones.txt` y `COMO_EJECUTAR.md`.
