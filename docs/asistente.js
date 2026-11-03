/* asistente.js — Motor determinista del asistente (versión web estática).
 * Misma lógica de intenciones que scripts/../asistente/motor.py.
 * Lee knowledge_base.json y responde SOLO con sus cifras. No inventa.
 * No requiere servidor ni instalación: corre en el navegador.
 */
"use strict";

let KB = null;

/* Minúsculas sin acentos, para comparar de forma robusta (como _norm en Python). */
function norm(texto) {
  return texto.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function detectarIntencion(q) {
  const qn = norm(q);
  const tiene = (arr) => arr.some((w) => qn.includes(w));
  // El orden importa: específicas antes que genéricas (idéntico a motor.py).
  if (tiene(["aire", "contaminacion", "pm2.5", "pm25", "pm 2.5", "particulas",
             "ambiental", "calidad del aire", "polucion", "siata", "respirar"]))
    return "ambiental";
  if (tiene(["tres territorios", "3 territorios", "presupuesto",
             "intervenir", "invertir", "priorizar", "priorizacion"]))
    return "priorizacion";
  if (tiene(["evolucion", "tendencia", "vario", "cambio", "aumento",
             "disminuyo", "entre 2012", "historico", "mejorado", "2012 y"]))
    return "tendencia";
  if (tiene(["fuente", "de donde", "datos reales"])) return "fuentes";
  if (tiene(["menor", "mas baja", "mejor"])) return "ranking_bottom";
  if (tiene(["mayor", "mas alta", "peor", "atencion", "mayores necesidades",
             "cuales comunas", "mortalidad", "defunciones", "muertes"]))
    return "ranking_top";
  return "desconocida";
}

function ranking() {
  return (((KB || {}).indicadores || {}).mortalidad_2022 || {}).ranking || [];
}

/* Construye los datos de un gráfico de barras a partir del ranking.
 * destacarIdx: índice a resaltar (o null). topN: si se da, resalta los primeros N. */
function graficoRanking(rank, destacarIdx, topN) {
  if (!rank || rank.length === 0) return null;
  const labels = rank.map((x) => x.nombre);
  const valores = rank.map((x) => x.tasa);
  const resaltar = rank.map((_, i) =>
    (topN != null ? i < topN : i === destacarIdx));
  return {
    tipo: "bar",
    titulo: "Tasa de mortalidad por territorio · Medellín 2022",
    etiqueta_eje: "Defunciones por 100.000 hab.",
    labels: labels,
    valores: valores,
    resaltar: resaltar,
  };
}

function responder(pregunta) {
  if (!KB) {
    return { respuesta_directa: "No se pudo cargar el knowledge base.",
             encontrado: false, evidencia: [] };
  }
  const intent = detectarIntencion(pregunta);
  const r = ranking();
  const necesitaRanking = ["ranking_top", "ranking_bottom",
                           "tendencia", "priorizacion"].includes(intent);
  if (necesitaRanking && r.length === 0) {
    return { respuesta_directa: "El indicador de mortalidad no está en el KB.",
             encontrado: false, evidencia: [] };
  }

  if (intent === "ranking_top") {
    const t = r[0];
    return {
      encontrado: true,
      respuesta_directa: `La comuna con mayor tasa de mortalidad en 2022 fue ${t.nombre} con ${t.tasa} defunciones por 100.000 habitantes (${t.casos} casos).`,
      evidencia: [{ indicador: "tasa de mortalidad", valor: t.tasa, anio: 2022,
                    territorio: t.nombre, fuente: "MEData - Secretaría de Salud" }],
      interpretacion: "Una tasa alta indica mayor carga de mortalidad relativa a su población; conviene priorizar seguimiento en este territorio.",
      recomendacion: `Priorizar programas de promoción y prevención en ${t.nombre}, con indicadores de seguimiento.`,
      limitaciones: "La tasa de mortalidad general depende de la estructura de edad de la comuna; es asociación, no causalidad.",
      grafico: graficoRanking(r, 0),
    };
  }

  if (intent === "ranking_bottom") {
    const b = r[r.length - 1];
    return {
      encontrado: true,
      respuesta_directa: `El territorio con menor tasa de mortalidad en 2022 fue ${b.nombre} con ${b.tasa} por 100.000 hab.`,
      evidencia: [{ indicador: "tasa de mortalidad", valor: b.tasa, anio: 2022,
                    territorio: b.nombre, fuente: "MEData - Secretaría de Salud" }],
      limitaciones: "Asociación, no causalidad; influye la estructura de edad.",
      grafico: graficoRanking(r, r.length - 1),
    };
  }

  if (intent === "priorizacion") {
    const top3 = r.slice(0, 3);
    return {
      encontrado: true,
      respuesta_directa: `Con criterio de mortalidad 2022, los tres territorios a priorizar serían: ${top3.map((x) => x.nombre).join(", ")}.`,
      evidencia: top3.map((x) => ({ indicador: "tasa de mortalidad", valor: x.tasa,
        anio: 2022, territorio: x.nombre, fuente: "MEData - Secretaría de Salud" })),
      interpretacion: "Son los de mayor tasa de mortalidad del período.",
      recomendacion: "Distribuir intervenciones según necesidad y definir indicadores para evaluar resultados.",
      limitaciones: "Priorización por un solo indicador; un índice multivariable (social+ambiental) sería más robusto.",
      grafico: graficoRanking(r, 0, 3),
    };
  }

  if (intent === "tendencia") {
    const h = ((KB.indicadores || {}).hallazgo_mortalidad) || {};
    const v = h.variacion_pct_2012_2022_comuna_top;
    const top = h.comuna_mayor_tasa || {};
    if (v === null || v === undefined) {
      return { respuesta_directa: "No hay serie temporal suficiente en el KB.",
               encontrado: false, evidencia: [] };
    }
    const signo = v >= 0 ? "aumentó" : "disminuyó";
    const serie = h.serie_temporal_comuna_top;
    let grafico = null;
    if (serie && serie.anios && serie.anios.length) {
      grafico = {
        tipo: "line",
        titulo: `Evolución de la tasa de mortalidad · ${top.nombre || ""} (${serie.anios[0]}–${serie.anios[serie.anios.length - 1]})`,
        etiqueta_eje: "Defunciones por 100.000 hab.",
        labels: serie.anios.map(String),
        valores: serie.tasas,
        resaltar: serie.anios.map(() => false),
      };
    }
    return {
      encontrado: true,
      respuesta_directa: `Entre 2012 y 2022, la tasa de mortalidad de ${top.nombre || "la comuna top"} ${signo} ${Math.abs(v)}%.`,
      evidencia: [{ indicador: "variación tasa mortalidad 2012-2022",
        valor: v + "%", territorio: top.nombre, fuente: "MEData - Secretaría de Salud" }],
      limitaciones: "Un cambio de tasa no explica sus causas por sí solo.",
      grafico: grafico,
    };
  }

  if (intent === "ambiental") {
    const pm = (KB.indicadores || {}).pm25_siata;
    if (!pm || !pm.ranking || pm.ranking.length === 0) {
      return {
        encontrado: false,
        respuesta_directa: "Aún no hay datos de PM2.5 (SIATA) en el knowledge base. Ejecuta el pipeline para incorporarlos.",
        evidencia: [],
      };
    }
    const top = pm.ranking[0];
    const grafico = {
      tipo: "bar",
      titulo: `PM2.5 promedio por estación · Medellín ${pm.anio}`,
      etiqueta_eje: "PM2.5 (µg/m³, media anual)",
      labels: pm.ranking.map((x) => x.estacion),
      valores: pm.ranking.map((x) => x.media_pm25),
      resaltar: pm.ranking.map((_, i) => i === 0),
    };
    return {
      encontrado: true,
      respuesta_directa: `En ${pm.anio}, la estación con mayor PM2.5 promedio fue ${top.estacion} con ${top.media_pm25} µg/m³. La medición de calidad del aire es por estación de monitoreo.`,
      evidencia: pm.ranking.slice(0, 5).map((x) => ({
        indicador: "PM2.5 media anual", valor: x.media_pm25, anio: pm.anio,
        territorio: "estación " + x.estacion, fuente: "SIATA" })),
      interpretacion: "Mayor PM2.5 implica peor calidad del aire en el entorno de esa estación; la exposición puede asociarse a afecciones respiratorias.",
      recomendacion: "Reforzar seguimiento y medidas preventivas en los periodos y zonas con mayor PM2.5.",
      limitaciones: pm.advertencia + " Además, una asociación con la salud no implica causalidad sin un diseño de estudio adecuado.",
      grafico: grafico,
    };
  }

  if (intent === "fuentes") {
    const f = KB.fuentes || {};
    const txt = Object.values(f).map((x) => `${x.nombre} (${x.entidad})`).join("; ");
    return {
      encontrado: true,
      respuesta_directa: `El proyecto usa datos reales de: ${txt}.`,
      evidencia: [{ indicador: "fuentes", valor: Object.keys(f), fuente: "pipeline" }],
    };
  }

  return {
    encontrado: false,
    respuesta_directa: "No identifiqué una consulta que pueda responder con los datos disponibles. Puedo responder sobre: comunas con mayor/menor mortalidad, priorización territorial, tendencia 2012-2022 y fuentes.",
    limitaciones: "El asistente solo responde con cifras del pipeline.",
    evidencia: [],
  };
}

async function cargarKB() {
  const resp = await fetch("knowledge_base.json", { cache: "no-store" });
  if (!resp.ok) throw new Error("No se pudo cargar knowledge_base.json");
  KB = await resp.json();
  return KB;
}

/* Exponer para el HTML. */
window.Asistente = { cargarKB, responder, detectarIntencion };
