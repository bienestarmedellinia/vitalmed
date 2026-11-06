/* asistente.js — Motor determinista del asistente (versión web estática).
 * Misma lógica de intenciones que scripts/../asistente/motor.py.
 * Lee knowledge_base.json y responde SOLO con sus cifras. No inventa.
 * No requiere servidor ni instalación: corre en el navegador.
 */
(function () {
"use strict";
// Ámbito propio: no declara globales que choquen con el script del portal.

let KB = null;

/* Minúsculas sin acentos, para comparar de forma robusta (como _norm en Python). */
function norm(texto) {
  return texto.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function detectarIntencion(q) {
  const qn = norm(q);
  const tiene = (arr) => arr.some((w) => qn.includes(w));
  // El orden importa: específicas antes que genéricas (idéntico a motor.py).
  if (tiene(["hallazgo", "conclusion principal", "resultado principal", "descubrimiento"]))
    return "hallazgo";
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

/* Detección de territorios (comunas/corregimientos) mencionados en la pregunta.
 * Idéntico a _territorios_en en motor.py. */
function aliasesTerritorio(nombre) {
  const n = norm(nombre);
  const out = new Set([n]);
  const sinArt = n.replace(/^(la|el|los|las) /, "");
  out.add(sinArt);
  const sinCorr = sinArt.replace(/^corregimiento de /, "");
  out.add(sinCorr);
  out.add(sinCorr.replace(/^san sebastian de /, ""));
  if (n.includes("laureles")) { out.add("laureles"); out.add("estadio"); }
  return [...out].filter((a) => a.length >= 4);
}

function territoriosEn(q) {
  const qn = " " + norm(q).replace(/[^a-z0-9 ]/g, " ").replace(/ +/g, " ") + " ";
  const hallados = [];
  ranking().forEach((t, i) => {
    let mejor = 0;
    aliasesTerritorio(t.nombre).forEach((a) => {
      if (qn.includes(" " + a + " ") && a.length > mejor) mejor = a.length;
    });
    if (mejor) hallados.push({ i: i, largo: mejor });
  });
  return hallados.sort((a, b) => b.largo - a.largo).slice(0, 2)
    .map((h) => h.i).sort((a, b) => a - b);
}

function pideCausa(q) {
  const qn = norm(q);
  return ["causa", "por que", "porque", "motivo", "razon", "explica",
          "factor", "se debe", "origen"].some((w) => qn.includes(w));
}

function medianaKB(arr) {
  const v = [...arr].sort((a, b) => a - b), m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

const SIN_CAUSA = "Los datos del proyecto no incluyen la causa específica de las defunciones (no hay desagregación por causa ni por edad), por lo que no puedo afirmar qué las causa. ";

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

  const idxTerr = (intent === "hallazgo" || intent === "ambiental" || intent === "fuentes")
    ? [] : territoriosEn(pregunta);
  const causa = pideCausa(pregunta);
  if (idxTerr.length && r.length) {
    const med = medianaKB(r.map((x) => x.tasa));
    const ind = ((KB.indicadores || {}).indice_priorizacion || {}).ranking || [];
    const h = (KB.indicadores || {}).hallazgo_mortalidad || {};
    const frases = [], ev = [];
    idxTerr.forEach((i) => {
      const t = r[i];
      let f = `${t.nombre}: tasa de mortalidad general 2022 de ${t.tasa} por 100.000 hab. (${t.casos} defunciones), puesto ${i + 1} de ${r.length} (1 = mayor tasa), ${(t.tasa / med).toFixed(2)} veces la mediana de los territorios (${med.toFixed(1)})`;
      const j = ind.findIndex((x) => x.comuna === t.comuna);
      if (j >= 0) f += `. Índice de priorización ${ind[j].indice} (puesto ${j + 1} de ${ind.length}); intento de suicidio ${ind[j].tasa_suicidio} por 100.000`;
      if (h.comuna_mayor_tasa && h.comuna_mayor_tasa.comuna === t.comuna && h.variacion_pct_2012_2022_comuna_top != null)
        f += `. Su tasa ${h.variacion_pct_2012_2022_comuna_top >= 0 ? "aumentó" : "disminuyó"} ${Math.abs(h.variacion_pct_2012_2022_comuna_top)}% entre 2012 y 2022`;
      frases.push(f + ".");
      ev.push({ indicador: "tasa de mortalidad", valor: t.tasa, anio: 2022, territorio: t.nombre, fuente: "MEData - Secretaría de Salud" });
      if (j >= 0) ev.push({ indicador: "índice de priorización", valor: ind[j].indice, anio: 2022, territorio: t.nombre, fuente: "MEData - Secretaría de Salud" });
    });
    const out = {
      encontrado: true,
      respuesta_directa: (causa ? SIN_CAUSA + "Lo que sí muestran los datos: " : "") + frases.join(" "),
      evidencia: ev,
      limitaciones: "Tasas brutas, sin estandarizar por edad; asociación, no causalidad.",
      grafico: graficoRanking(r, idxTerr[0]),
    };
    if (out.grafico) out.grafico.resaltar = r.map((_, i) => idxTerr.includes(i));
    if (causa) {
      out.interpretacion = "Una tasa alta describe cuánto se muere, no por qué. Posibles factores a verificar (hipótesis, no demostradas con estos datos): estructura de edad de la población, condiciones sociales del territorio y salud mental (el índice incluye intento de suicidio).";
      out.recomendacion = "Para identificar causas: pedir a MEData/Secretaría de Salud las defunciones por causa (CIE-10) y grupo de edad por comuna, y estandarizar las tasas por edad.";
    } else {
      out.interpretacion = "La posición y la razón frente a la mediana permiten ubicar al territorio dentro de la ciudad.";
    }
    return out;
  }

  if (causa && !necesitaRanking && intent === "desconocida" && r.length) {
    const t = r[0];
    return {
      encontrado: true,
      respuesta_directa: SIN_CAUSA + `Lo que sí muestran: la mayor tasa 2022 está en ${t.nombre} (${t.tasa} por 100.000 hab.) y la menor en ${r[r.length - 1].nombre} (${r[r.length - 1].tasa}). Pregunta por un territorio concreto, p. ej. «¿Qué sabemos de mortalidad en ${t.nombre}?».`,
      evidencia: [{ indicador: "tasa de mortalidad", valor: t.tasa, anio: 2022, territorio: t.nombre, fuente: "MEData - Secretaría de Salud" }],
      interpretacion: "El análisis es descriptivo y territorial: identifica dónde se concentra la mortalidad, no su causa.",
      recomendacion: "Pedir defunciones por causa (CIE-10) y edad para un análisis causal o estandarizado.",
      limitaciones: "Asociación, no causalidad.",
      grafico: graficoRanking(r, 0),
    };
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
    const idx = (KB.indicadores || {}).indice_priorizacion;
    if (idx && idx.ranking && idx.ranking.length) {
      const top3 = idx.ranking.slice(0, 3);
      const comps = (idx.componentes || []).join(" + ");
      const grafico = {
        tipo: "bar",
        titulo: `Índice de priorización en salud por comuna · Medellín ${idx.anio}`,
        etiqueta_eje: "Índice (0–100, mayor = más prioritario)",
        labels: idx.ranking.map((x) => x.nombre),
        valores: idx.ranking.map((x) => x.indice),
        resaltar: idx.ranking.map((_, i) => i < 3),
      };
      return {
        encontrado: true,
        respuesta_directa: `Según el índice multivariable de priorización en salud (${comps}, normalizados 0-100), los tres territorios a priorizar son: ${top3.map((x) => x.nombre).join(", ")} (índice: ${top3.map((x) => x.indice).join(", ")}).`,
        evidencia: top3.map((x) => ({ indicador: "índice de priorización",
          valor: x.indice, anio: idx.anio, territorio: x.nombre,
          fuente: idx.fuente || "MEData" })),
        interpretacion: "El índice combina dos dimensiones de salud por comuna (mortalidad y salud mental), cada una normalizada; un valor alto refleja prioridad en más de un indicador, no en uno solo.",
        recomendacion: "Concentrar intervenciones intersectoriales en los territorios de mayor índice y monitorear ambos componentes.",
        limitaciones: "El índice combina solo indicadores de salud medidos por comuna (MEData). El PM2.5 (SIATA) es por estación y se reporta como contexto ambiental aparte, no dentro del índice. Asociación, no causalidad.",
        grafico: grafico,
      };
    }
    // Fallback: priorización por mortalidad si no hay índice.
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

  if (intent === "hallazgo") {
    const h = (KB.indicadores || {}).hallazgo_mortalidad || {};
    const top = h.comuna_mayor_tasa, bajo = h.comuna_menor_tasa, v = h.variacion_pct_2012_2022_comuna_top;
    if (!top || !bajo) {
      return { respuesta_directa: "El hallazgo principal no está en el KB.", encontrado: false, evidencia: [] };
    }
    const anio = h.anio_referencia || 2022, fuente = "MEData - Secretaría de Salud";
    const ev = [
      { indicador: "tasa de mortalidad", valor: top.tasa, anio: anio, territorio: top.nombre, fuente: fuente },
      { indicador: "brecha vs menor tasa", valor: h.brecha_veces + "x", anio: anio, territorio: bajo.nombre, fuente: fuente },
    ];
    if (v !== null && v !== undefined)
      ev.push({ indicador: "variación tasa 2012-2022", valor: v + "%", territorio: top.nombre, fuente: fuente });
    return {
      encontrado: true,
      respuesta_directa: `Hallazgo principal: ${top.nombre} tiene la mayor tasa de mortalidad (${top.tasa} por 100.000 hab., ${anio}), ${h.brecha_veces} veces la de ${bajo.nombre} (${bajo.tasa})` +
        (v !== null && v !== undefined ? `, y aumentó ${v}% entre 2012 y 2022.` : "."),
      evidencia: ev,
      interpretacion: "La brecha territorial es grande y persistente: el lugar de residencia se asocia con la carga de mortalidad.",
      recomendacion: "Priorizar intervenciones intersectoriales en los territorios de mayor índice de priorización y monitorear su evolución.",
      limitaciones: "Tasas brutas, sin estandarizar por edad. Asociación, no causalidad.",
      grafico: graficoRanking(r, 0),
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

  const nombres = r.slice(0, 3).map((x) => x.nombre).join(", ");
  return {
    encontrado: false,
    respuesta_directa: "No identifiqué una consulta que pueda responder con los datos disponibles. Prueba con: «¿Qué sabemos de la mortalidad en " + (r[0] ? r[0].nombre : "La Candelaria") + "?», «¿Qué comunas priorizar?», «¿Cómo varió la mortalidad entre 2012 y 2022?», «¿Qué relación hay entre el aire y la salud?» o «¿De dónde vienen los datos?». También puedes nombrar un territorio (" + nombres + "…).",
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

/* ── Interpretación con IA (opcional) ───────────────────────────────────
 * Solo se usa si el motor determinista NO entendió la pregunta. El Worker
 * (worker/src/index.js, Gemini) devuelve SOLO {intencion, territorios, causa};
 * con eso se arma una consulta canónica y la responde el MISMO motor
 * determinista: las cifras siempre salen del KB, nunca de la IA.
 * Si IA_URL está vacío, falla o tarda, se devuelve la respuesta determinista. */
const IA_URL = "";
const CLAVE_INTENCION = {
  hallazgo: "hallazgo principal", ambiental: "calidad del aire",
  priorizacion: "priorizar", tendencia: "tendencia", fuentes: "fuentes",
  ranking_top: "mayor mortalidad", ranking_bottom: "menor mortalidad",
  territorio: "", fuera_de_alcance: "",
};
const NOMBRE_INTENCION = {
  hallazgo: "hallazgo principal", ambiental: "calidad del aire",
  priorizacion: "priorización territorial", tendencia: "tendencia en el tiempo",
  fuentes: "fuentes de datos", ranking_top: "territorios con mayor mortalidad",
  ranking_bottom: "territorios con menor mortalidad", territorio: "consulta por territorio",
};

async function interpretarIA(pregunta) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 9000);
  try {
    const r = await fetch(IA_URL, { method: "POST", signal: ctrl.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pregunta: pregunta.slice(0, 300) }) });
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    return null;
  } finally {
    clearTimeout(t);
  }
}

/* Consulta canónica a partir de la interpretación (solo valores de listas cerradas). */
function consultaCanonica(i) {
  const terr = (i.territorios || []).filter((t) => ranking().some((x) => x.nombre === t));
  return [...terr, CLAVE_INTENCION[i.intencion] || "", i.causa ? "causa" : ""]
    .join(" ").trim();
}

/* Con IA activa, toda pregunta escrita se interpreta primero con IA (corrige
 * errores, apodos y falsos positivos de palabras clave). Si la IA falla, tarda,
 * o la considera fuera de alcance, se usa la respuesta determinista. */
async function responderConIA(pregunta) {
  const base = responder(pregunta);
  if (!IA_URL || !KB) return base;
  const i = await interpretarIA(pregunta);
  if (!i || !i.intencion || i.intencion === "fuera_de_alcance") return base;
  const q = consultaCanonica(i);
  if (!q) return base;
  const r = responder(q);
  if (!r.encontrado) return base;
  const partes = [NOMBRE_INTENCION[i.intencion], (i.territorios || []).join(" y "),
                  i.causa ? "pregunta por causas" : ""].filter(Boolean);
  r.via_ia = `Interpreté tu pregunta con IA (Gemini) como: ${partes.join(" · ")}. Las cifras provienen de la base de conocimiento, no de la IA.`;
  return r;
}

/* Exponer para el HTML. */
window.Asistente = { cargarKB, responder, responderConIA, detectarIntencion,
                     consultaCanonica, iaActiva: () => !!IA_URL };
})();
