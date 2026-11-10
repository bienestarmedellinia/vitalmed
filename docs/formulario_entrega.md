# Formulario de entrega — Hackathon de Datos 2026 (ITM)

> Fuente de referencia para diligenciar el **formulario oficial del ITM**. Los textos están
> redactados con datos reales del proyecto (verificados contra `instrucciones.txt`, `equipo.yml`
> y `outputs/tablas/hallazgo.json`). Copiar/pegar cada sección en el formulario correspondiente.
>
> Proyecto: **Bienestar Medellín IA — Vitalmed** · Equipo: **MCC GLOBAL SOLUTIONS** · Categoría: **Interna**
> Modalidad: **Pipeline automático (principal) + Visualización (valor agregado)**
> Entrega: **martes 10 de noviembre de 2026, 5:30 p.m.**

---

## Sección 1 · Identificación

| Campo | Valor |
|---|---|
| Nombre del equipo | MCC GLOBAL SOLUTIONS |
| Nombre del proyecto | Bienestar Medellín IA — Vitalmed |
| Categoría | Interna (ITM) |
| Modalidad | Pipeline automático + Visualización |
| Líder | Walter Andrés Tabares |
| Correo del líder | waltertabares31943@correo.itm.edu.co |
| Teléfono del líder | 3505137553 |
| Integrante 1 | Walter Andrés Tabares · ITM · Ingeniería de Sistemas (9° semestre) · Líder |
| Integrante 2 | Jorge Alexander Marin · ITM · Ingeniería de Sistemas (9° semestre) · Integrante |
| Repositorio público | https://github.com/bienestarmedellinia/vitalmed |
| Portal / Observatorio (LIVE) | https://bienestarmedellinia.github.io/vitalmed/ |

---

## Sección 2 · Problema, pregunta y usuario

**Problema que aborda el proyecto**

El bienestar en Medellín no se distribuye de forma homogénea entre sus territorios. Existe una
brecha territorial medible en salud y en condiciones sociales y ambientales: hay comunas con tasas
de mortalidad varias veces superiores a las de otros territorios de la misma ciudad. Esa desigualdad
está dispersa en múltiples fuentes oficiales (salud, calidad del aire, condiciones de vida), con
formatos, niveles territoriales y periodicidades distintos, lo que dificulta verla de forma integrada
y oportuna para la toma de decisiones. El dato existe, pero no está consolidado ni es fácil de explorar.

**Pregunta de investigación**

¿Cómo pueden las técnicas de análisis de datos identificar y explicar la influencia de los factores
ambientales, sociales y territoriales sobre las condiciones de salud y bienestar de Medellín, con el
fin de apoyar la toma de decisiones y la formulación de intervenciones basadas en evidencia?

**Usuario objetivo**

Tomadores de decisión del sector público de Medellín (Secretaría de Salud, Planeación y entidades
afines), analistas y equipos técnicos que necesitan priorizar territorios e intervenciones, y la
ciudadanía interesada en el estado del bienestar de su comuna. El producto está diseñado para ser
usado sin instalar nada ni iniciar sesión: basta abrir el portal web y explorar.

---

## Sección 3 · Solución, valor, hallazgo y limitaciones

**Solución propuesta**

Un **pipeline automático** (modalidad principal) que descarga, valida, integra y analiza datos
oficiales de **6 fuentes** (MEData, ECV, SIATA, DANE, SIVIGILA y RIPS) sobre salud y bienestar por
comuna de Medellín, más un **observatorio web** (valor agregado) que presenta los resultados de forma
interactiva. El observatorio es **100 % determinista**: todas las cifras, textos e interpretaciones se
recuperan de un *knowledge base* generado por el pipeline, sin consultar modelos de lenguaje en tiempo
de ejecución ni enviar datos a terceros al navegar.

El pipeline combina mortalidad e intento de suicidio por comuna (MEData) en un **índice de priorización
territorial en salud**, reporta la calidad del aire (PM2.5, SIATA) como contexto ambiental por estación,
usa la ECV como llave y cobertura territorial, y calcula factores asociados (correlaciones entre
territorios). Todo el cómputo pesado corre en GitHub Actions de forma reproducible y automática.

**Valor / aporte**

- **Consolidación e integración**: reúne en un solo lugar 6 fuentes oficiales dispersas (~39 indicadores),
  con su cobertura, licencia y fuente a la vista.
- **Automatización verificable**: el pipeline se ejecuta solo (por *push*, programado y manual) y deja
  evidencia pública de cada ejecución; los resultados se versionan automáticamente.
- **Priorización basada en evidencia**: el índice multivariable permite ordenar territorios para focalizar
  intervenciones, con transparencia metodológica.
- **Accesibilidad**: observatorio público, explorable y con descargas abiertas (CSV), sin requerir cuenta.

**Hallazgo principal** (verificado, `outputs/tablas/hallazgo.json`)

La Candelaria (comuna 10) presenta la mayor tasa de mortalidad general de la ciudad en 2022:
**1.325,6 defunciones por 100.000 habitantes** (1.074 casos), **4,58 veces** la del corregimiento de
Santa Elena (289,5 por 100.000). Entre 2012 y 2022 la tasa de La Candelaria creció **+44,6 %**. En el
índice de priorización en salud 2022 (promedio normalizado de mortalidad general + intento de suicidio),
el *top 3* es **La Candelaria (100,0), Laureles-Estadio (62,2) y Manrique (61,0)** — Manrique entra por
el componente de salud mental, no por mortalidad, lo que muestra el valor de un índice multivariable
frente a mirar un solo indicador.

**Limitaciones (declaradas con honestidad)**

- **Asociación, no causalidad**: las correlaciones y el índice son descriptivos; no controlan por
  estructura de edad ni por confusores. La mortalidad bruta correlaciona negativamente con algunos
  indicadores sociales por un efecto de composición por edad (se declara en el KB).
- **Nivel territorial mixto**: MEData y ECV llegan a comuna; DANE, SIVIGILA y RIPS son a nivel de
  municipio (Medellín), con periodicidad distinta (mensual/semanal/anual). No se mezclan ni se atribuyen
  a comunas.
- **Cobertura temporal de la fuente**: MEData no publica por comuna después de 2022; ECV social llega a
  2022 (empleo/ocupación a 2019); SIATA PM2.5 2020–2025; DANE 2020–2024; SIVIGILA 2008–2022; RIPS
  2009–2021. No hay datos 2026. Es limitación de la **fuente**, no del pipeline.
- **COVID-19 (2020–2021)** actúa como confusor en varias series.
- **Sin desglose por sexo** (el KB no lo expone); el único desglose etario disponible es la mortalidad
  DANE por grupo de edad.

---

## Sección 4 · Uso de MEData (fuente obligatoria)

| Campo | Detalle |
|---|---|
| Conjunto de datos | VC_Datos_Enfermedades (Secretaría de Salud de Medellín) — 10 capas por comuna |
| Enlace al servicio | https://www.medellin.gov.co/servidormapas/rest/services/salud_protec_soc/VC_Datos_Enfermedades/MapServer |
| Portal MEData | https://medata.app.medellin.gov.co/ |
| Fecha de consulta | 6 de noviembre de 2026 |
| Licencia | Atribución 4.0 Internacional (CC BY 4.0) |
| Atribución | Alcaldía de Medellín, Secretaría de Salud, MEData |

**Variables utilizadas**

Las 10 capas por comuna (códigos de comuna `01`–`16` y corregimientos `50/60/70/80/90`; se excluye el
código `99` "Sin información"), campos `casos_YYYY`, `naciviv_YYYY` y `tasa_YYYY` (tasas por 100.000 hab.):
mortalidad general (2012–2022), intento de suicidio (2013–2022), natalidad, dengue, hepatitis A,
parotiditis, tosferina, tuberculosis pulmonar, varicela (2008–2022) y violencia de género (2013–2022).
Fichas de licencia verificadas: mortalidad (id 1-026-22-000161) e intento de suicidio
(id 1-026-22-000146, registros SIVIGILA), ambas de la Secretaría de Salud / UGIC.

**Dificultades encontradas**

- El servicio ArcGIS responde **403** sin un *User-Agent* de navegador; hubo que configurarlo en la descarga.
- MEData **no publica estas capas por comuna después de 2022** (verificado en vivo, nov. 2026), lo que limita
  la cobertura más reciente por territorio.
- El conjunto "afiliados régimen contributivo" (node/16534) **no sirve**: entrega un CSV alojado en una IP
  privada inaccesible; se descartó.

**¿Qué no se pudo responder con MEData?**

- Análisis por **grupo de edad o sexo a nivel de comuna** (MEData expone tasas agregadas por comuna, sin esos
  desgloses) → se complementó parcialmente con la mortalidad por grupo de edad del DANE, pero a nivel municipal.
- Series por comuna **posteriores a 2022** (la fuente dejó de publicarlas a ese nivel).

**Propuesta de apertura / mejora de datos**

Que MEData publique las capas por comuna de forma **continua y actualizada** (posterior a 2022) y, de ser
posible, con **desglose por grupo de edad y sexo** a nivel de comuna, lo que permitiría calcular tasas
estandarizadas por edad y análisis de equidad más finos. Igualmente, estandarizar formatos y una licencia
explícita y uniforme en el centro documental para las bases ECV 2022–2025.

---

## Sección 5 · Repositorio, prueba e IA

**Repositorio**

- Código (público): https://github.com/bienestarmedellinia/vitalmed
- Portal / observatorio (LIVE): https://bienestarmedellinia.github.io/vitalmed/
- Explorador de datos (LIVE): https://bienestarmedellinia.github.io/vitalmed/datos.html

**Prueba que debe hacer el jurado** (sin cuenta, sin instalar nada)

1. **Portal**: abrir https://bienestarmedellinia.github.io/vitalmed/ y explorar el mapa y las 13
   categorías con su análisis técnico.
2. **Automatización (evidencia del pipeline)**: abrir el historial **filtrado** del workflow principal
   https://github.com/bienestarmedellinia/vitalmed/actions/workflows/pipeline.yml — muestra solo las
   ejecuciones de "pipeline-principal"; cada fila con **check** (✓) es una ejecución correcta. Abrir una
   ejecución y hacer clic en "pipeline" muestra las etapas en orden (dentro el check se ve gris = hecho).
   Los disparadores (al abrir el YAML) acreditan que corre sin intervención: *push* a main,
   `workflow_dispatch` (manual) y `schedule` (automático diario ~6 a.m. y mensual).
3. **Resultados**: abrir https://github.com/bienestarmedellinia/vitalmed/tree/main/outputs (carpetas
   `graficos`, `kb`, `tablas`) — son los archivos que el pipeline genera en cada ejecución.

Nota: el botón "Run workflow" (ejecución en vivo) solo aparece para usuarios con permiso e iniciados sesión;
en la sustentación es **el equipo** quien lanza una ejecución en vivo. El jurado acredita la automatización
con el historial y los disparadores del YAML.

**Uso de inteligencia artificial** (ver detalle en `instrucciones.txt` §7)

- **Kiro CLI** (asistente de programación con IA): apoyo en el **desarrollo** — escritura y refactorización
  de los scripts del pipeline, el portal web y la documentación. El equipo revisa, ejecuta y puede explicar
  todo el resultado.
- **Observatorio del portal y motor CLI** (`docs/portal.js`, `asistente/motor.py`): deterministas, de
  reglas; recuperan las cifras del *knowledge base* del pipeline. **No inventan datos**, **no consultan LLM
  en tiempo de ejecución** y **no envían datos a terceros** al navegar.
- **Opcional, desactivado por defecto**: `asistente/llm.py` puede usar un modelo de OpenAI (gpt-4o-mini)
  **solo** si existe `OPENAI_API_KEY`, y únicamente para redactar con más fluidez una respuesta ya calculada
  por el motor. No genera cifras ni se usa en el portal publicado.
- **ChatGPT y Gemini**: consultas exploratorias puntuales en la etapa inicial (ideas y búsqueda de fuentes).
  No generaron el código, las cifras ni los análisis del artefacto; el desarrollo se hizo con Kiro CLI y el
  equipo verificó cada fuente contra los portales oficiales.

---

## Sección 6 · Otras fuentes de datos

| Fuente | Enlace | Fecha de consulta | Licencia | Rol |
|---|---|---|---|---|
| ECV — Encuesta de Calidad de Vida (microdatos) | https://www.medellin.gov.co/es/centro-documental/encuesta-calidad-de-vida/ | 6 nov. 2026 | CC BY 4.0 (ficha MEData id 1-002-09-000040); bases 2022–2025 sin licencia explícita → se atribuye | Llave y cobertura territorial (21 territorios) |
| ECV — Serie histórica de indicadores (2007–2022) | https://www.medellin.gov.co/es/wp-content/uploads/2023/01/Serie-Historica-Indicadores_24052023.xlsx | 6 nov. 2026 | Alcaldía de Medellín (Planeación) | 21 indicadores sociales por territorio |
| SIATA — PM2.5 (datos validados) | https://siata.gov.co/IDEAM/ | 6 nov. 2026 | Condiciones en el sitio de SIATA (sin licencia explícita) → se atribuye | Contexto ambiental por estación (2020–2025) |
| DANE — Estadísticas Vitales (EEVV) | https://microdatos.dane.gov.co/index.php/catalog/central?sk=Estad%C3%ADsticas%20Vitales | 6 nov. 2026 | Uso público con cita obligatoria al DANE | Mortalidad mensual por causa CIE-10 y edad (2020–2024) |
| SIVIGILA (INS) vía datos.gov.co | https://www.datos.gov.co/d/4hyg-wa9d | 6 nov. 2026 | CC BY-SA 4.0 | ESI-IRAG e intento de suicidio semanal (2008–2022) |
| RIPS (MinSalud) vía datos.gov.co | https://www.datos.gov.co/d/4k9h-8qiu | 6 nov. 2026 | CC BY-SA 4.0 | Morbilidad anual por CIE-10 (2009–2021) |

Nota metodológica: DANE, SIVIGILA y RIPS son a nivel de municipio (Medellín), no por comuna, y con
periodicidades distintas; se muestran por separado, sin mezclarse ni atribuirse a comunas. 2020–2021
reflejan la COVID-19. Los microdatos no se publican; solo se publican tablas agregadas por comuna, sin
datos personales.

---

## Sección 7 · Checklist de entrega

- [x] Repositorio público con artefacto funcionando (portal + explorador + pipeline verde).
- [x] `instrucciones.txt` (inicio rápido de 3 pasos + detalle técnico).
- [x] `ficha_hallazgos.pdf` generado por el pipeline (sin campos "[POR COMPLETAR]").
- [x] Uso de MEData documentado (fuente obligatoria) + otras 5 fuentes declaradas.
- [x] Datos reales (no sintéticos), sin PII, repo público, artefacto corre.
- [x] Declaración de uso de IA.
- [ ] Copia del carné estudiantil de cada integrante (documento personal — lo adjunta el usuario).
- [ ] (Solo finalistas) Resumen de pitch de 1 página.

---

*Contacto:* Walter Andrés Tabares (líder) · waltertabares31943@correo.itm.edu.co · 3505137553
