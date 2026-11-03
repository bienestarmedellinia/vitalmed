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
