# Medellín, Bienestar Basado en Datos

Proyecto para la **Hackathon de Datos 2026 · Institución Universitaria ITM**.
Modalidad: **Pipeline automático**. Temática: **Salud y bienestar**.

> *¿Cómo podemos utilizar el análisis de datos para identificar los factores
> ambientales, sociales y territoriales que afectan la salud y el bienestar de
> los habitantes de Medellín?*

## Qué hace

Un pipeline que, sin intervención manual, **descarga** datos oficiales,
**valida** su consistencia, los **homologa** e **integra** en una tabla por
comuna y corregimiento. Se ejecuta íntegramente en **GitHub Actions**.

```
scripts/
  sources.yml        Manifiesto de URLs oficiales (ECV, SIATA, MEData)
  01_descargar.py    Descarga desde la fuente oficial -> data/raw/
  03_validar.py      Valida la llave territorial (16 comunas + 5 corregimientos)
  02_limpiar.py      Homologa p_006 / P_007 / A.7 -> territorio_cod
  04_integrar.py     Tabla agregada publicable -> outputs/tablas/
.github/workflows/
  pipeline.yml       Orquesta los 4 pasos en el runner
```

## Fuentes

| Fuente | Dimensión | Enlace |
|--------|-----------|--------|
| ECV (Alcaldía de Medellín) | Social, salud, territorial | https://www.medellin.gov.co/es/centro-documental/encuesta-calidad-de-vida/ |
| SIATA | Ambiental (PM2.5) | https://siata.gov.co/IDEAM/ |
| MEData | Sanitaria (obligatoria) | https://medata.app.medellin.gov.co/ |

## Privacidad

Las bases ECV son microdatos a nivel de persona. **No se versionan** en el
repositorio (ver `.gitignore`): el pipeline los descarga en tiempo de ejecución.
Solo se publican **tablas agregadas** por territorio, sin datos personales,
conforme a la Cláusula de Ética y Transparencia de la Hackathon.

## Nota de arquitectura

El desarrollo local se hace en una Raspberry Pi, que **no procesa los datos**
(leer las bases completas la satura). Todo el cómputo pesado corre en GitHub
Actions. La RPi solo edita código y hace `git push`.

## Cómo ejecutarlo

Ver `instrucciones.txt`.

## Hallazgo principal

> En 2022, **La Candelaria (comuna 10)** presentó la **mayor tasa de mortalidad
> de Medellín: 1.325,6 defunciones por 100.000 habitantes**, equivalente a
> **4,6 veces** la del territorio con menor tasa (corregimiento de Santa Elena,
> 289,5). Entre 2012 y 2022 su tasa **aumentó +44,6%**.

Fuente: MEData — Secretaría de Salud de Medellín (servicio `VC_Datos_Enfermedades`),
datos agregados por comuna, sin datos personales. Los 21 territorios oficiales
(16 comunas + 5 corregimientos); se excluye la categoría residual "Sin información".

Artefactos generados por el pipeline (descargables desde la pestaña Actions):
- `outputs/tablas/hallazgo.json` — la cifra principal para la ficha de entrega.
- `outputs/tablas/analisis_mortalidad_comuna.csv` — ranking completo por comuna.
- `outputs/graficos/ranking_mortalidad_2022.png` — ranking por comuna.
- `outputs/graficos/evolucion_comuna_top.png` — serie temporal 2012–2022.
- `outputs/graficos/pipeline.png` — diagrama del funcionamiento del pipeline.

> Nota metodológica: una asociación territorial no implica causalidad. La tasa
> de mortalidad general está influida por la estructura de edad de cada comuna
> (p. ej. La Candelaria y Laureles tienen población más envejecida).


## Fase 2 — Asistente de inteligencia territorial

Sobre los resultados del pipeline se construye un asistente que responde
preguntas en lenguaje natural **usando solo las cifras verificadas** del
knowledge base (`outputs/kb/knowledge_base.json`). No inventa datos.

Arquitectura en dos capas:

1. **Motor determinista** (`asistente/motor.py`) — sin IA, sin API key.
   Detecta la intención de la pregunta y recupera la cifra del KB. **Siempre
   funciona**, por lo que el jurado puede ejecutarlo sin configurar nada.
2. **Capa LLM opcional** (`asistente/llm.py`) — si existe `OPENAI_API_KEY`,
   mejora la redacción tomando *solo* las cifras ya recuperadas (no genera
   números). Sin la key, se omite y responde el motor determinista.
3. **Explorador de datos** (`docs/datos.html`) — módulo independiente del
   asistente: tablas, gráficos y CSV de todos los indicadores por territorio y
   año, factores asociados y PM2.5. Archivos abiertos en `docs/datos/`
   (generados por `07_construir_kb.py` desde el mismo KB).
4. **Interpretación con IA en el portal web** (`worker/`) — un Worker de
   Cloudflare usa Gemini para clasificar la pregunta escrita (intención y
   territorios, de listas cerradas; nunca cifras). Luego responde el motor
   determinista. Despliegue y verificación: `worker/README.md`.

Cada respuesta entrega: respuesta directa · evidencia (indicador, valor, año,
territorio, fuente) · interpretación · recomendación · limitaciones.

Uso:

```bash
# 1) generar el knowledge base (si no está): usa las tablas del pipeline
python scripts/07_construir_kb.py

# 2a) interfaz web (fase 2):
pip install -r asistente/requirements.txt
streamlit run asistente/app.py

# 2b) modo CLI de respaldo (no requiere streamlit):
python asistente/app.py --cli "¿Qué comunas priorizar en salud?"

# pruebas del asistente (verifican que responde con cifras reales):
python asistente/test_motor.py
```

El asistente es liviano (solo lee un JSON pequeño), por lo que corre sin
problema en la Raspberry Pi; el cómputo pesado sigue siendo del pipeline.
