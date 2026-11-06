/* asistente.js — Motor determinista del asistente (versión web estática).
 * PARIDAD: misma lógica y mismos textos que asistente/motor.py (lo verifica
 * asistente/test_motor.py comparando ambas salidas).
 * Lee knowledge_base.json y responde SOLO con sus cifras. No inventa.
 * Cubre todas las series del KB: 10 indicadores de salud MEData por comuna,
 * la serie histórica de indicadores ECV y PM2.5 por estación (SIATA).
 */
(function () {
"use strict";
// Ámbito propio: no declara globales que choquen con el script del portal.

let KB = null;
const F_MEDATA = "MEData - Secretaría de Salud";

/* ── Utilidades (idénticas en motor.py) ─────────────────────────────── */
function norm(texto) {
  return String(texto).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}
function limpio(q) {
  return " " + norm(q).replace(/[^a-z0-9. ]/g, " ").replace(/ +/g, " ").trim() + " ";
}
function tiene(qn, arr) { return arr.some((w) => qn.includes(w)); }
/* Número con hasta 2 decimales, sin ceros sobrantes. */
function num(x) {
  if (Number.isInteger(x)) return String(x);
  return x.toFixed(2).replace(/\.?0+$/, "");
}
function fx(x, d) { return x.toFixed(d); }
function conSigno(x, d) { return (x > 0 ? "+" : "") + x.toFixed(d); }
function mediana(arr) {
  const v = [...arr].sort((a, b) => a - b), m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}
function ordenNum(a, b) { return Number(a) - Number(b); }

/* ── Acceso al KB ───────────────────────────────────────────────────── */
function S() { return (KB || {}).series || null; }
function catalogo() { return (S() || {}).catalogo || []; }
function info(clave) { return catalogo().find((c) => c.clave === clave) || null; }
function datos(clave) { return ((S() || {}).datos || {})[clave] || null; }
function rankingMort() {
  return (((KB || {}).indicadores || {}).mortalidad_2022 || {}).ranking || [];
}
function territorios() {
  const t = (S() || {}).territorios;
  if (t) return Object.keys(t).sort(ordenNum).map((c) => ({ cod: c, nombre: t[c] }));
  return rankingMort().map((x) => ({ cod: String(x.comuna), nombre: x.nombre }));
}
function nombreTerr(cod) {
  const t = territorios().find((x) => x.cod === String(cod));
  return t ? t.nombre : String(cod);
}
function esSalud(c) { return c.dimension === "salud"; }
function etiqueta(c) {
  return esSalud(c) ? "tasa de " + c.nombre : c.nombre.charAt(0).toLowerCase() + c.nombre.slice(1);
}
/* Valores de un indicador en un año, de mayor a menor. */
function valoresAnio(clave, anio) {
  const d = datos(clave);
  if (!d) return [];
  const a = String(anio), out = [];
  territorios().forEach((t) => {
    const v = (d.valores[t.cod] || {})[a];
    if (v !== undefined && v !== null) {
      const cs = d.casos ? (d.casos[t.cod] || {})[a] : undefined;
      out.push({ cod: t.cod, nombre: t.nombre, valor: v, casos: cs });
    }
  });
  return out.sort((x, y) => y.valor - x.valor || ordenNum(x.cod, y.cod));
}
/* Año a usar: el pedido si existe; si no, el más cercano, con nota. */
function resolverAnio(c, pedido) {
  const anios = c.anios, ult = anios[anios.length - 1];
  if (pedido == null) return { anio: ult, nota: "" };
  if (anios.includes(pedido)) return { anio: pedido, nota: "" };
  const usado = pedido > ult ? ult : (pedido < anios[0] ? anios[0] :
    anios.reduce((b, a) => (Math.abs(a - pedido) < Math.abs(b - pedido) ? a : b), ult));
  const extra = esSalud(c) ? " (MEData publica estas series por comuna hasta " + ult + ")" : "";
  return { anio: usado, nota: `${capital(c.nombre)} tiene datos de ${anios[0]} a ${ult}${extra}; no hay dato para ${pedido}. Muestro ${usado}. ` };
}
function capital(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
function limitacion(c) {
  return esSalud(c)
    ? "Tasas brutas, sin estandarizar por edad; asociación, no causalidad."
    : "Estimación por encuesta (muestra): diferencias pequeñas entre territorios pueden no ser significativas. Asociación, no causalidad.";
}
function fuenteDe(c) { return esSalud(c) ? F_MEDATA : "ECV - serie histórica (Planeación)"; }

/* ── Detección ──────────────────────────────────────────────────────── */
const KW_TENDENCIA = ["evolucion", "evoluciono", "tendencia", "vario", "cambio", "aumento",
  "disminuyo", "entre 2012", "historico", "historia", "mejorado", "empeor", "2012 y", "cambiad",
  "con los anos", "a lo largo", "en el tiempo", "serie"];
const KW_AYUDA = ["que preguntas", "que puedo preguntar", "que te puedo", "que le puedo",
  "ayuda", "que sabes", "que puedes", "como funciona", "que informacion", "que datos tienes",
  "que datos hay", "que temas", "como te uso", "como se usa", "ejemplos de preguntas", "menu",
  "hola", "buenas", "que haces"];
const KW_AIRE = ["aire", "contaminacion", "pm2.5", "pm25", "pm 2.5", "particulas",
  "ambiental", "calidad del aire", "polucion", "siata", "respirar", "respira", "smog"];
const KW_FACTORES = ["factores", "asociad", "se relaciona", "relacionad", "correlac",
  "que influye", "influencia", "determinantes", "explica"];

function detectarIntencion(q) {
  const qn = norm(q);
  // El orden importa: específicas antes que genéricas (idéntico a motor.py).
  if (tiene(qn, KW_AYUDA)) return "ayuda";
  if (tiene(qn, ["hallazgo", "conclusion principal", "resultado principal", "descubrimiento"]))
    return "hallazgo";
  if (tiene(qn, KW_AIRE)) return "ambiental";
  if (tiene(qn, KW_FACTORES)) return "factores";
  if (tiene(qn, ["tres territorios", "3 territorios", "presupuesto",
                 "intervenir", "invertir", "priorizar", "priorizacion"]))
    return "priorizacion";
  if (tiene(qn, KW_TENDENCIA)) return "tendencia";
  if (tiene(qn, ["fuente", "de donde", "datos reales", "licencia"])) return "fuentes";
  if (tiene(qn, ["menor", "mas baja", "mejor", "menos"])) return "ranking_bottom";
  if (tiene(qn, ["mayor", "mas alta", "peor", "atencion", "mayores necesidades",
                 "cuales comunas", "ranking", "mas casos"]))
    return "ranking_top";
  return "desconocida";
}

function pideCausa(q) {
  return tiene(norm(q), ["causa", "por que", "porque", "motivo", "razon", "se debe", "origen"]);
}

function detectarAnios(q) {
  const out = [];
  (norm(q).match(/\b(19|20)\d{2}\b/g) || []).forEach((a) => {
    const n = Number(a);
    if (!out.includes(n)) out.push(n);
  });
  return out;
}

/* Sinónimos de los indicadores de salud (MEData). */
const SINONIMOS = [
  ["intento_suicidio", ["suicid", "salud mental"]],
  ["violencia_genero", ["violencia de genero", "violencia genero", "violencia contra la mujer", "violencia contra las mujeres"]],
  ["tuberculosis_pulmonar", ["tuberculosis"]],
  ["hepatitis_a", ["hepatitis"]],
  ["parotiditis", ["parotiditis", "paperas"]],
  ["tosferina", ["tosferina", "tos ferina"]],
  ["varicela", ["varicela"]],
  ["dengue", ["dengue"]],
  ["natalidad", ["natalidad", "nacimiento", "nacidos", "nacen", "fecundidad"]],
  ["mortalidad", ["mortalidad", "moratilidad", "mortalid", "defuncion", "muerte", "mueren",
                  "muere", "murieron", "fallec"]],
];
/* Conceptos frecuentes -> fragmento del nombre del indicador ECV. */
const ALIAS_ECV = [
  [["desemple", "sin empleo", "paro"], "desempleo abierto"],
  [["hambre", "inseguridad alimentaria", "comida", "alimentacion"], "algun nivel de inseguridad alimentaria"],
  [["analfabet", "leer y escribir"], "analfabetismo de 15 y mas"],
  [["escolaridad", "educacion", "estudian", "colegio"], "neta de escolaridad todos los niveles"],
  [["dependencia"], "dependencia economica"],
  [["ocupacion", "empleo", "trabajo"], "tasa ocupacion"],
  [["deporte", "deportiv", "ejercicio", "actividad fisica"], "practica actividades deportivas"],
  [["cultura"], "programas culturales"],
  [["planificacion", "anticoncep", "planifica"], "que planifica"],
  [["masculinidad"], "masculinidad"],
  [["jefas de hogar", "mujeres cabeza", "jefatura femenina"], "mujeres jefes cabeza de hogar"],
];
const VACIAS = new Set(["comuna", "comunas", "territorio", "territorios", "barrio", "medellin",
  "ciudad", "datos", "tasa", "tasas", "porcentaje", "poblacion", "personas", "hogares", "hogar",
  "indicador", "indicadores", "cuanto", "cuantos", "cuales", "donde", "tiene", "tienen", "entre",
  "sobre", "segun", "valor", "valores", "nivel", "niveles", "mayor", "menor", "total", "sabemos",
  "situacion", "informacion", "quiero", "saber", "puedo", "preguntar", "preguntas",
  "corregimiento", "corregimientos", "comparar", "compara", "priorizar", "salud", "general",
  "cuanta", "cuantas", "estado", "como", "esta", "estan", "fueron", "hubo", "habia", "grave",
  "jefes", "calificado", "informante", "anos", "cada"]);

function palabras(t) {
  return norm(t).split(/[^a-z0-9]+/).filter((w) => w.length >= 5 && !VACIAS.has(w));
}

function detectarIndicador(q) {
  const qn = norm(q), cat = catalogo();
  if (tiene(qn, KW_AIRE)) return "pm25";
  // 1) Nombre completo del indicador (el más largo primero).
  const porNombre = cat.filter((c) => qn.includes(norm(c.nombre)))
    .sort((a, b) => b.nombre.length - a.nombre.length);
  if (porNombre.length) return porNombre[0].clave;
  // 2) Sinónimos de salud.
  for (const [clave, ws] of SINONIMOS)
    if (tiene(qn, ws) && info(clave)) return clave;
  // 3) Conceptos ECV frecuentes.
  for (const [ws, frag] of ALIAS_ECV) {
    if (!tiene(qn, ws)) continue;
    const c = cat.find((x) => !esSalud(x) && norm(x.nombre).includes(frag));
    if (c) return c.clave;
  }
  // 4) Coincidencia de raíces (5 letras) con nombres de indicadores ECV.
  const raices = new Set(palabras(q).map((w) => w.slice(0, 5)));
  if (!raices.size) return null;
  let mejor = null, puntos = 0;
  cat.filter((c) => !esSalud(c)).forEach((c) => {
    const p = new Set(palabras(c.nombre).map((w) => w.slice(0, 5)));
    const n = [...raices].filter((r) => p.has(r)).length;
    if (n > puntos || (n === puntos && n > 0 && c.nombre.length < mejor.nombre.length)) {
      mejor = c; puntos = n;
    }
  });
  return puntos > 0 ? mejor.clave : null;
}

/* Variantes del nombre de un territorio (igual que _aliases en motor.py). */
function aliasesTerritorio(nombre) {
  const n = norm(nombre);
  const out = new Set([n]);
  const sinArt = n.replace(/^(la|el|los|las) /, "");
  out.add(sinArt);
  const sinCorr = sinArt.replace(/^corregimiento de /, "");
  out.add(sinCorr);
  out.add(sinCorr.replace(/^san sebastian de /, ""));
  if (n.includes("laureles")) { out.add("laureles"); out.add("estadio"); }
  if (n.includes("candelaria")) out.add("el centro");
  if (n.includes("doce de octubre")) out.add("12 de octubre");
  if (n.includes("villa hermosa")) out.add("villahermosa");
  return [...out].filter((a) => a.length >= 4);
}

/* Códigos (texto) de hasta 2 territorios mencionados, en orden de aparición. */
function territoriosEn(q) {
  const qn = limpio(q).replace(/\./g, " ");
  const hallados = [];
  territorios().forEach((t) => {
    let pos = -1, largo = 0;
    aliasesTerritorio(t.nombre).forEach((a) => {
      const p = qn.indexOf(" " + a + " ");
      if (p >= 0 && a.length > largo) { pos = p; largo = a.length; }
    });
    const m = qn.match(new RegExp(" (comuna|corregimiento) " + t.cod + " "));
    if (m && pos < 0) { pos = m.index; largo = m[0].length; }
    if (pos >= 0) hallados.push({ cod: t.cod, pos: pos, largo: largo });
  });
  return hallados.sort((a, b) => b.largo - a.largo).slice(0, 2)
    .sort((a, b) => a.pos - b.pos).map((h) => h.cod);
}

/* ── Gráficos ───────────────────────────────────────────────────────── */
function graficoBarras(c, anio, vals, resaltarCods) {
  return {
    tipo: "bar",
    titulo: `${capital(etiqueta(c))} por territorio · Medellín ${anio}`,
    etiqueta_eje: c.unidad || c.nombre,
    labels: vals.map((x) => x.nombre),
    valores: vals.map((x) => x.valor),
    resaltar: vals.map((x) => resaltarCods.includes(x.cod)),
  };
}
function graficoLinea(titulo, eje, anios, series) {
  return { tipo: "line", titulo: titulo, etiqueta_eje: eje, labels: anios.map(String),
           valores: series[0].valores, series: series, resaltar: anios.map(() => false) };
}

/* ── Respuestas ─────────────────────────────────────────────────────── */
const SIN_CAUSA = "Los datos del proyecto no incluyen la causa específica de las defunciones (no hay desagregación por causa ni por edad), por lo que no puedo afirmar qué las causa. ";
const SIN_CAUSA_GEN = "Los datos del proyecto describen cuánto ocurre en cada territorio, no por qué ocurre, así que no puedo afirmar causas. ";
const REC_CAUSAS = "Para identificar causas: pedir a MEData/Secretaría de Salud las defunciones por causa (CIE-10) y grupo de edad por comuna, y estandarizar las tasas por edad.";

function noEncontrado(texto) {
  return { encontrado: false, respuesta_directa: texto, evidencia: [],
           limitaciones: "El asistente solo responde con cifras del pipeline." };
}

/* Correlaciones significativas para un indicador (como resultado o como factor). */
function asociados(clave, maximo) {
  const corr = (S() || {}).correlaciones || [];
  let lista = corr.filter((x) => x.resultado === clave)
    .map((x) => ({ otro: x.factor, r: x.pearson, rho: x.spearman, anio: x.anio, n: x.n, sig: x.significativa }));
  if (!lista.length)
    lista = corr.filter((x) => x.factor === clave)
      .map((x) => ({ otro: x.resultado, r: x.pearson, rho: x.spearman, anio: x.anio, n: x.n, sig: x.significativa }));
  lista = lista.filter((x) => info(x.otro));
  lista.sort((a, b) => Math.abs(b.r) - Math.abs(a.r) || (a.otro < b.otro ? -1 : 1));
  const sig = lista.filter((x) => x.sig);
  return { sig: sig.slice(0, maximo), todos: lista.slice(0, maximo) };
}
function nombreCorto(c) {
  return esSalud(c) ? c.nombre : c.nombre.charAt(0).toLowerCase() + c.nombre.slice(1);
}
function textoAsociado(a) {
  return `${nombreCorto(info(a.otro))} (r = ${conSigno(a.r, 2)} en ${a.anio}, ${a.r > 0 ? "misma dirección" : "dirección opuesta"})`;
}

function resAyuda() {
  const cat = catalogo(), sal = cat.filter(esSalud), soc = cat.filter((c) => !esSalud(c));
  const rango = (l) => `${Math.min(...l.map((c) => c.anios[0]))}–${Math.max(...l.map((c) => c.anios[c.anios.length - 1]))}`;
  const pm = ((KB.indicadores || {}).pm25_siata) || {};
  const anPm = Object.keys(pm.promedio_estaciones || {}).sort();
  let cob = "";
  if (sal.length) cob += `${sal.length} indicadores de salud por comuna (MEData, ${rango(sal)}: ${sal.map((c) => c.nombre).join(", ")})`;
  const temas = [...new Set(soc.map((c) => c.tema))].sort();
  if (soc.length) cob += `${cob ? ", " : ""}${soc.length} indicadores sociales de la Encuesta de Calidad de Vida (${rango(soc)}: ${temas.join(", ")})`;
  if (anPm.length) cob += `${cob ? " y " : ""}PM2.5 por estación de SIATA (${anPm[0]}–${anPm[anPm.length - 1]})`;
  const ej = ["¿Qué comuna tiene la mayor mortalidad?", "¿Cómo está Manrique?",
    "¿Cómo evolucionó el dengue en Robledo?", "Tasa de intento de suicidio en Belén en 2018",
    "¿Qué factores se asocian a la mortalidad?", "Compara Popular y El Poblado",
    "¿Dónde hay más inseguridad alimentaria?", "¿Cómo ha cambiado el aire?",
    "¿Qué territorios priorizar?", "¿De dónde vienen los datos?"];
  return {
    encontrado: true,
    respuesta_directa: `Puedo responder con ${cob || "los datos del KB"}, para los 21 territorios (16 comunas y 5 corregimientos). Pregunta por un indicador, un territorio y/o un año. Ejemplos: ${ej.map((e) => "«" + e + "»").join(" ")}`,
    evidencia: [],
    interpretacion: "Puedes combinar: indicador (mortalidad, dengue, desempleo…), territorio (nombre o «comuna 10») y año. Si el año no existe, te digo el rango disponible.",
    limitaciones: "No hay datos individuales ni causas de muerte; las cifras son agregadas por territorio.",
  };
}

function resFuentes() {
  const f = KB.fuentes || {};
  const txt = Object.values(f).map((x) => {
    let s = `${x.nombre} (${x.entidad}`;
    if (x.serie) s += `, ${x.serie}`;
    if (x.serie_historica) s += `, serie histórica ${x.serie_historica}`;
    if (x.indicadores) s += `, ${x.indicadores} indicadores`;
    return s + ")";
  }).join("; ");
  return { encontrado: true, respuesta_directa: `El proyecto usa datos reales de: ${txt}.`,
           evidencia: [{ indicador: "fuentes", valor: Object.keys(f), fuente: "pipeline" }] };
}

function resHallazgo() {
  const h = (KB.indicadores || {}).hallazgo_mortalidad || {}, r = rankingMort();
  const top = h.comuna_mayor_tasa, bajo = h.comuna_menor_tasa, v = h.variacion_pct_2012_2022_comuna_top;
  if (!top || !bajo) return noEncontrado("El hallazgo principal no está en el KB.");
  const anio = h.anio_referencia || 2022;
  const ev = [
    { indicador: "tasa de mortalidad", valor: top.tasa, anio: anio, territorio: top.nombre, fuente: F_MEDATA },
    { indicador: "brecha vs menor tasa", valor: h.brecha_veces + "x", anio: anio, territorio: bajo.nombre, fuente: F_MEDATA },
  ];
  if (v !== null && v !== undefined)
    ev.push({ indicador: "variación tasa 2012-2022", valor: v + "%", territorio: top.nombre, fuente: F_MEDATA });
  const c = info("mortalidad");
  return {
    encontrado: true,
    respuesta_directa: `Hallazgo principal: ${top.nombre} tiene la mayor tasa de mortalidad (${num(top.tasa)} por 100.000 hab., ${anio}), ${num(h.brecha_veces)} veces la de ${bajo.nombre} (${num(bajo.tasa)})` +
      (v !== null && v !== undefined ? `, y aumentó ${num(v)}% entre 2012 y 2022.` : "."),
    evidencia: ev,
    interpretacion: "La brecha territorial es grande y persistente: el lugar de residencia se asocia con la carga de mortalidad.",
    recomendacion: "Priorizar intervenciones intersectoriales en los territorios de mayor índice de priorización y monitorear su evolución.",
    limitaciones: "Tasas brutas, sin estandarizar por edad. Asociación, no causalidad.",
    grafico: c ? graficoBarras(c, anio, valoresAnio("mortalidad", anio), [String(top.comuna)]) : null,
  };
}

function resPriorizacion() {
  const idx = (KB.indicadores || {}).indice_priorizacion;
  if (!idx || !idx.ranking || !idx.ranking.length) {
    const r = rankingMort();
    if (!r.length) return noEncontrado("El indicador de mortalidad no está en el KB.");
    const top3 = r.slice(0, 3);
    return {
      encontrado: true,
      respuesta_directa: `Con criterio de mortalidad 2022, los tres territorios a priorizar serían: ${top3.map((x) => x.nombre).join(", ")}.`,
      evidencia: top3.map((x) => ({ indicador: "tasa de mortalidad", valor: x.tasa, anio: 2022, territorio: x.nombre, fuente: F_MEDATA })),
      interpretacion: "Son los de mayor tasa de mortalidad del período.",
      recomendacion: "Distribuir intervenciones según necesidad y definir indicadores para evaluar resultados.",
      limitaciones: "Priorización por un solo indicador; un índice multivariable (social+ambiental) sería más robusto.",
    };
  }
  const top3 = idx.ranking.slice(0, 3), comps = (idx.componentes || []).join(" + ");
  return {
    encontrado: true,
    respuesta_directa: `Según el índice multivariable de priorización en salud (${comps}, normalizados 0-100), los tres territorios a priorizar son: ${top3.map((x) => x.nombre).join(", ")} (índice: ${top3.map((x) => num(x.indice)).join(", ")}).`,
    evidencia: top3.map((x) => ({ indicador: "índice de priorización", valor: x.indice, anio: idx.anio, territorio: x.nombre, fuente: idx.fuente || "MEData" })),
    interpretacion: "El índice combina dos dimensiones de salud por comuna (mortalidad y salud mental), cada una normalizada; un valor alto refleja prioridad en más de un indicador, no en uno solo.",
    recomendacion: "Concentrar intervenciones intersectoriales en los territorios de mayor índice y monitorear ambos componentes.",
    limitaciones: "El índice combina solo indicadores de salud medidos por comuna (MEData). El PM2.5 (SIATA) es por estación y se reporta como contexto ambiental aparte, no dentro del índice. Asociación, no causalidad.",
    grafico: { tipo: "bar", titulo: `Índice de priorización en salud por comuna · Medellín ${idx.anio}`,
               etiqueta_eje: "Índice (0–100, mayor = más prioritario)",
               labels: idx.ranking.map((x) => x.nombre), valores: idx.ranking.map((x) => x.indice),
               resaltar: idx.ranking.map((_, i) => i < 3) },
  };
}

function resAmbiental(anios, tendencia) {
  const pm = (KB.indicadores || {}).pm25_siata;
  if (!pm || !pm.ranking || !pm.ranking.length)
    return noEncontrado("Aún no hay datos de PM2.5 (SIATA) en el knowledge base. Ejecuta el pipeline para incorporarlos.");
  const lim = pm.advertencia + " Además, una asociación con la salud no implica causalidad sin un diseño de estudio adecuado.";
  const prom = pm.promedio_estaciones || {}, ap = Object.keys(prom).sort();
  if ((tendencia || anios.length >= 2) && ap.length >= 2) {
    let ini = ap[0], fin = ap[ap.length - 1];
    if (anios.length >= 2) {
      const a = String(Math.min(...anios)), b = String(Math.max(...anios));
      if (prom[a] !== undefined) ini = a;
      if (prom[b] !== undefined) fin = b;
    }
    const sel = ap.filter((a) => a >= ini && a <= fin);
    const v0 = prom[ini], v1 = prom[fin], pct = (v1 / v0 - 1) * 100;
    return {
      encontrado: true,
      respuesta_directa: `El promedio anual de PM2.5 de las estaciones SIATA pasó de ${num(v0)} µg/m³ en ${ini} a ${num(v1)} µg/m³ en ${fin} (${conSigno(pct, 1)}%). La guía de la OMS es 5 µg/m³: en ${fin} el promedio la supera ${fx(v1 / 5, 1)} veces.`,
      evidencia: sel.map((a) => ({ indicador: "PM2.5 promedio de estaciones", valor: prom[a], anio: Number(a), territorio: "estaciones SIATA", fuente: "SIATA" })),
      interpretacion: "La tendencia resume el promedio simple de las estaciones con datos válidos cada año (años completos).",
      recomendacion: "Sostener las medidas que reducen el PM2.5 y vigilar las estaciones que empeoran.",
      limitaciones: lim + " " + (pm.criterio || ""),
      grafico: graficoLinea("PM2.5 promedio de estaciones SIATA (µg/m³)", "µg/m³ (media anual)",
        sel.map(Number), [{ nombre: "Promedio estaciones", valores: sel.map((a) => prom[a]) }]),
    };
  }
  let nota = "", ranking = pm.ranking, anio = pm.anio;
  if (anios.length) {
    const pedido = anios[0], serie = pm.serie || {};
    const disp = [...new Set(Object.values(serie).flatMap((x) => Object.keys(x)))].sort();
    if (disp.includes(String(pedido))) {
      anio = pedido;
      ranking = Object.keys(serie).filter((e) => serie[e][String(pedido)] !== undefined)
        .map((e) => ({ estacion: e, media_pm25: serie[e][String(pedido)] }))
        .sort((a, b) => b.media_pm25 - a.media_pm25 || (a.estacion < b.estacion ? -1 : 1));
    } else if (pedido !== pm.anio) {
      nota = `PM2.5 tiene medias anuales válidas para ${disp.join(", ")}; no para ${pedido}. Muestro ${pm.anio}. `;
    }
  }
  const top = ranking[0];
  const pa = prom[String(anio)];
  return {
    encontrado: true,
    respuesta_directa: `${nota}En ${anio}, la estación con mayor PM2.5 promedio fue ${top.estacion} con ${num(top.media_pm25)} µg/m³. La medición de calidad del aire es por estación de monitoreo.` +
      (pa !== undefined ? ` Promedio de estaciones: ${num(pa)} µg/m³ (guía OMS: 5).` : ""),
    evidencia: ranking.slice(0, 5).map((x) => ({ indicador: "PM2.5 media anual", valor: x.media_pm25, anio: anio, territorio: "estación " + x.estacion, fuente: "SIATA" })),
    interpretacion: "Mayor PM2.5 implica peor calidad del aire en el entorno de esa estación; la exposición puede asociarse a afecciones respiratorias.",
    recomendacion: "Reforzar seguimiento y medidas preventivas en los periodos y zonas con mayor PM2.5.",
    limitaciones: lim,
    grafico: { tipo: "bar", titulo: `PM2.5 promedio por estación · Medellín ${anio}`, etiqueta_eje: "PM2.5 (µg/m³, media anual)",
               labels: ranking.map((x) => x.estacion), valores: ranking.map((x) => x.media_pm25),
               resaltar: ranking.map((_, i) => i === 0) },
  };
}

function resFactores(clave, causa) {
  const c = info(clave);
  const as = asociados(clave, 5);
  if (!c || !as.todos.length)
    return noEncontrado("No hay correlaciones calculadas para ese indicador en el KB.");
  const lista = as.sig.length ? as.sig : as.todos.slice(0, 3);
  const intro = causa ? (clave === "mortalidad" ? SIN_CAUSA : SIN_CAUSA_GEN) + "Lo que sí muestran los datos: " : "";
  const cuerpo = as.sig.length
    ? `entre los 21 territorios, la ${etiqueta(c)} se asocia de forma estadísticamente apreciable con: ${lista.map(textoAsociado).join("; ")}.`
    : `entre los 21 territorios, ninguna correlación con la ${etiqueta(c)} supera el umbral aproximado del 95%; las más altas son: ${lista.map(textoAsociado).join("; ")}.`;
  return {
    encontrado: true,
    respuesta_directa: intro + capital(cuerpo),
    evidencia: lista.map((a) => ({ indicador: "correlación con " + c.nombre + ": " + info(a.otro).nombre,
      valor: conSigno(a.r, 2), anio: a.anio, territorio: a.n + " territorios", fuente: "cálculo propio (MEData + ECV)" })),
    interpretacion: (S() || {}).nota_correlaciones || "",
    recomendacion: REC_CAUSAS,
    limitaciones: "Correlación de Pearson (confirmada con Spearman) en el año más reciente común a ambos indicadores. Asociación, no causalidad.",
    grafico: { tipo: "bar", titulo: `Factores asociados a la ${etiqueta(c)} (correlación entre territorios)`,
               etiqueta_eje: "r de Pearson (−1 a 1)", labels: lista.map((a) => info(a.otro).nombre.slice(0, 60)),
               valores: lista.map((a) => a.r), resaltar: lista.map((a) => a.r > 0) },
  };
}

function resRanking(clave, anios, abajo) {
  const c = info(clave);
  if (!c) return noEncontrado("El indicador no está en el KB.");
  const ra = resolverAnio(c, anios.length ? anios[0] : null);
  const vals = valoresAnio(clave, ra.anio);
  if (!vals.length) return noEncontrado("No hay datos de ese indicador para ese año.");
  const sel = abajo ? [...vals].reverse() : vals, t = sel[0];
  const cs = t.casos !== undefined && t.casos !== null ? ` (${t.casos} casos)` : "";
  const sig = sel.slice(1, 3).map((x) => `${x.nombre} (${num(x.valor)})`).join(" y ");
  const ciu = ((datos(clave) || {}).ciudad || {})[String(ra.anio)];
  let txt = `${ra.nota}En ${ra.anio}, el territorio con ${abajo ? "menor" : "mayor"} ${etiqueta(c)} fue ${t.nombre} con ${num(t.valor)} ${c.unidad}${cs}.`;
  if (sig) txt += ` Le siguen ${sig}.`;
  if (ciu !== undefined) txt += ` Medellín: ${num(ciu)}.`;
  return {
    encontrado: true,
    respuesta_directa: txt,
    evidencia: sel.slice(0, 5).map((x) => ({ indicador: c.nombre, valor: x.valor, anio: ra.anio, territorio: x.nombre, fuente: fuenteDe(c) })),
    interpretacion: esSalud(c)
      ? "Una tasa alta indica mayor carga relativa a la población del territorio; conviene priorizar seguimiento allí."
      : "Un valor alto no siempre es negativo: depende de lo que mida el indicador.",
    recomendacion: esSalud(c) ? `Priorizar programas de promoción y prevención en ${t.nombre}, con indicadores de seguimiento.` : "",
    limitaciones: limitacion(c),
    grafico: graficoBarras(c, ra.anio, vals, [t.cod]),
  };
}

function resTendencia(clave, cods, anios) {
  const c = info(clave), d = datos(clave);
  if (!c || !d) return noEncontrado("No hay serie temporal suficiente en el KB.");
  let ini = c.anios[0], fin = c.anios[c.anios.length - 1], nota = "";
  if (anios.length >= 2) {
    const a = Math.min(...anios), b = Math.max(...anios);
    const ra = resolverAnio(c, a), rb = resolverAnio(c, b);
    ini = ra.anio; fin = rb.anio; nota = ra.nota + rb.nota;
  }
  const rango = c.anios.filter((a) => a >= ini && a <= fin);
  const quien = [];
  const h = (KB.indicadores || {}).hallazgo_mortalidad || {};
  // Sin territorio y con el rango completo de mortalidad: se conserva el hallazgo
  // (variación de la comuna con mayor tasa) junto a la serie de la ciudad.
  const compat = clave === "mortalidad" && !cods.length && ini === c.anios[0] &&
    fin === c.anios[c.anios.length - 1] && h.variacion_pct_2012_2022_comuna_top != null;
  if (cods.length) cods.forEach((k) => quien.push({ nombre: nombreTerr(k), serie: d.valores[k] || {} }));
  else if (compat) quien.push({ nombre: h.comuna_mayor_tasa.nombre, serie: d.valores[String(h.comuna_mayor_tasa.comuna)] || {} });
  if (!cods.length && d.ciudad) quien.push({ nombre: "Medellín (21 territorios)", serie: d.ciudad });
  if (!quien.length) {
    const top = valoresAnio(clave, fin)[0];
    if (top) quien.push({ nombre: top.nombre, serie: d.valores[top.cod] });
  }
  const frases = [], ev = [];
  quien.forEach((q) => {
    const an = rango.filter((a) => q.serie[String(a)] !== undefined);
    if (an.length < 2) return;
    const a0 = an[0], a1 = an[an.length - 1], v0 = q.serie[String(a0)], v1 = q.serie[String(a1)];
    let mx = an[0], mn = an[0];
    an.forEach((a) => { if (q.serie[String(a)] > q.serie[String(mx)]) mx = a; if (q.serie[String(a)] < q.serie[String(mn)]) mn = a; });
    let f = `${q.nombre}: la ${etiqueta(c)} pasó de ${num(v0)} en ${a0} a ${num(v1)} en ${a1}`;
    if (v0) f += ` (${conSigno((v1 / v0 - 1) * 100, 1)}%)`;
    f += `; máximo ${num(q.serie[String(mx)])} en ${mx} y mínimo ${num(q.serie[String(mn)])} en ${mn}.`;
    frases.push(f);
    ev.push({ indicador: c.nombre + " " + a0, valor: v0, anio: a0, territorio: q.nombre, fuente: fuenteDe(c) });
    ev.push({ indicador: c.nombre + " " + a1, valor: v1, anio: a1, territorio: q.nombre, fuente: fuenteDe(c) });
  });
  if (!frases.length) return noEncontrado("No hay serie temporal suficiente en el KB.");
  let txt = nota;
  if (compat) {
    const v = h.variacion_pct_2012_2022_comuna_top;
    txt += `Entre 2012 y 2022, la tasa de mortalidad de ${h.comuna_mayor_tasa.nombre} ${v >= 0 ? "aumentó" : "disminuyó"} ${num(Math.abs(v))}%. `;
  }
  txt += frases.join(" ");
  const series = quien.map((q) => ({ nombre: q.nombre, valores: rango.map((a) => (q.serie[String(a)] !== undefined ? q.serie[String(a)] : null)) }));
  return {
    encontrado: true,
    respuesta_directa: txt,
    evidencia: ev,
    interpretacion: rango.includes(2020) && rango.includes(2021) && esSalud(c)
      ? "Los años 2020–2021 coinciden con la pandemia de COVID-19, que alteró la mortalidad y la notificación de eventos."
      : "",
    limitaciones: "Un cambio de tasa no explica sus causas por sí solo. " + limitacion(c),
    grafico: graficoLinea(`Evolución: ${etiqueta(c)} (${rango[0]}–${rango[rango.length - 1]})`, c.unidad || c.nombre, rango, series),
  };
}

function resTerritorio(cods, clave, anios, causa) {
  const c = info(clave);
  if (!c) return noEncontrado("El indicador no está en el KB.");
  const ra = resolverAnio(c, anios.length ? anios[0] : null), anio = ra.anio;
  const vals = valoresAnio(clave, anio);
  if (!vals.length) return noEncontrado("No hay datos de ese indicador para ese año.");
  const med = mediana(vals.map((x) => x.valor));
  const d = datos(clave), idx = (KB.indicadores || {}).indice_priorizacion || {};
  const ind = idx.ranking || [];
  const frases = [], ev = [];
  cods.forEach((k) => {
    const i = vals.findIndex((x) => x.cod === k);
    const nom = nombreTerr(k);
    if (i < 0) { frases.push(`${nom}: sin dato de ${c.nombre} en ${anio}.`); return; }
    const t = vals[i];
    const cs = t.casos !== undefined && t.casos !== null ? ` (${t.casos} casos)` : "";
    let f = `${nom}: ${etiqueta(c)} ${anio} de ${num(t.valor)} ${c.unidad}${cs}, puesto ${i + 1} de ${vals.length} (1 = valor más alto), ${med ? fx(t.valor / med, 2) : "–"} veces la mediana de los territorios (${fx(med, 1)})`;
    const j = ind.findIndex((x) => String(x.comuna) === k);
    if (clave === "mortalidad" && j >= 0 && anio === idx.anio)
      f += `. Índice de priorización ${num(ind[j].indice)} (puesto ${j + 1} de ${ind.length}); intento de suicidio ${num(ind[j].tasa_suicidio)} por 100.000`;
    const serie = d.valores[k] || {}, a0 = c.anios.find((a) => serie[String(a)] !== undefined);
    if (a0 !== undefined && a0 < anio && serie[String(a0)]) {
      const pct = (t.valor / serie[String(a0)] - 1) * 100;
      f += `. Entre ${a0} y ${anio} ${pct >= 0 ? "aumentó" : "disminuyó"} ${fx(Math.abs(pct), 1)}%`;
    }
    frases.push(f + ".");
    ev.push({ indicador: c.nombre, valor: t.valor, anio: anio, territorio: nom, fuente: fuenteDe(c) });
    if (clave === "mortalidad" && j >= 0 && anio === idx.anio)
      ev.push({ indicador: "índice de priorización", valor: ind[j].indice, anio: anio, territorio: nom, fuente: F_MEDATA });
  });
  const ciu = (d.ciudad || {})[String(anio)];
  let txt = ra.nota + (causa ? (clave === "mortalidad" ? SIN_CAUSA : SIN_CAUSA_GEN) + "Lo que sí muestran los datos: " : "") + frases.join(" ");
  if (ciu !== undefined) txt += ` Medellín: ${num(ciu)}.`;
  const out = {
    encontrado: true,
    respuesta_directa: txt,
    evidencia: ev,
    interpretacion: "La posición y la razón frente a la mediana permiten ubicar al territorio dentro de la ciudad.",
    recomendacion: "",
    limitaciones: limitacion(c),
    grafico: graficoBarras(c, anio, vals, cods),
  };
  if (causa) {
    const as = asociados(clave, 3);
    let interp = "Una tasa alta describe cuánto ocurre, no por qué. ";
    if (as.sig.length) interp += `Factores asociados entre territorios (correlación, no causalidad): ${as.sig.map(textoAsociado).join("; ")}. `;
    interp += "Hipótesis a verificar, no demostradas con estos datos: estructura de edad de la población, condiciones sociales del territorio y salud mental.";
    out.interpretacion = interp;
    out.recomendacion = REC_CAUSAS;
  }
  return out;
}

/* forzado (opcional): interpretación ya hecha por la IA
 * {intencion, indicador, territorios[nombres], anios[], causa}. */
function responder(pregunta, forzado) {
  if (!KB) return { respuesta_directa: "No se pudo cargar el knowledge base.", encontrado: false, evidencia: [] };
  const qn = norm(pregunta);
  let intent, clave, cods, anios, causa;
  if (forzado) {
    intent = forzado.intencion || "desconocida";
    if (intent === "fuera_de_alcance") intent = "desconocida";
    if (intent === "territorio") intent = "desconocida";
    clave = forzado.indicador && (forzado.indicador === "pm25" || info(forzado.indicador)) ? forzado.indicador : null;
    const nombres = (forzado.territorios || []).map(norm);
    cods = territorios().filter((t) => nombres.includes(norm(t.nombre))).map((t) => t.cod).slice(0, 2);
    anios = (forzado.anios || []).filter((a) => Number.isInteger(a) && a >= 1990 && a <= 2100).slice(0, 2);
    causa = !!forzado.causa;
  } else {
    intent = detectarIntencion(pregunta);
    clave = detectarIndicador(pregunta);
    cods = territoriosEn(pregunta);
    anios = detectarAnios(pregunta);
    causa = pideCausa(pregunta);
  }
  if (intent === "ambiental") clave = "pm25";

  if (intent === "ayuda") return resAyuda();
  if (intent === "hallazgo") return resHallazgo();
  if (intent === "fuentes") return resFuentes();
  if (clave === "pm25") return resAmbiental(anios, intent === "tendencia" || tiene(qn, KW_TENDENCIA));
  if (!catalogo().length) return noEncontrado("El knowledge base no tiene series por indicador. Ejecuta el pipeline.");
  if (intent === "factores" && cods.length) return resTerritorio(cods, clave || "mortalidad", anios, true);
  if (intent === "factores" || (causa && !cods.length)) return resFactores(clave || "mortalidad", causa);
  if (intent === "priorizacion" && !cods.length) return resPriorizacion();
  if (intent === "tendencia" || (anios.length >= 2 && intent !== "ranking_top" && intent !== "ranking_bottom"))
    return resTendencia(clave || "mortalidad", cods, anios);
  if (cods.length) return resTerritorio(cods, clave || "mortalidad", anios, causa);
  if (intent === "ranking_top" || intent === "ranking_bottom")
    return resRanking(clave || "mortalidad", anios, intent === "ranking_bottom");
  if (clave) return resRanking(clave, anios, false);
  if (anios.length) return resRanking("mortalidad", anios, false);
  const t0 = rankingMort()[0];
  return noEncontrado("No identifiqué una consulta que pueda responder con los datos disponibles. Escribe «¿Qué preguntas puedo hacer?» para ver ejemplos, o prueba con: «¿Qué sabemos de la mortalidad en " + (t0 ? t0.nombre : "La Candelaria") + "?», «¿Qué comunas priorizar?», «¿Cómo evolucionó el dengue?» o «¿Qué relación hay entre el aire y la salud?».");
}

async function cargarKB() {
  const resp = await fetch("knowledge_base.json", { cache: "no-store" });
  if (!resp.ok) throw new Error("No se pudo cargar knowledge_base.json");
  KB = await resp.json();
  return KB;
}

/* ── Interpretación con IA (opcional) ───────────────────────────────────
 * El Worker (worker/src/index.js, Gemini) devuelve SOLO
 * {intencion, territorios, indicador, anios, causa}, de listas cerradas.
 * Con eso responde el MISMO motor determinista: las cifras salen del KB.
 * Si IA_URL está vacío, falla o tarda, se devuelve la respuesta determinista. */
const IA_URL = "https://bienestar-medellin-ia.watabares.workers.dev/interpretar";
const NOMBRE_INTENCION = {
  hallazgo: "hallazgo principal", ambiental: "calidad del aire",
  priorizacion: "priorización territorial", tendencia: "tendencia en el tiempo",
  fuentes: "fuentes de datos", ranking_top: "territorios con valores más altos",
  ranking_bottom: "territorios con valores más bajos", territorio: "consulta por territorio",
  factores: "factores asociados", ayuda: "ayuda",
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

/* Con IA activa, toda pregunta escrita se interpreta primero con IA (corrige
 * errores, apodos y falsos positivos de palabras clave). Si la IA falla, tarda,
 * o la considera fuera de alcance, se usa la respuesta determinista. */
async function responderConIA(pregunta) {
  const base = responder(pregunta);
  if (!IA_URL || !KB) return base;
  const i = await interpretarIA(pregunta);
  if (!i || !i.intencion || i.intencion === "fuera_de_alcance") return base;
  const r = responder(pregunta, i);
  if (!r.encontrado) return base;
  const c = i.indicador === "pm25" ? { nombre: "PM2.5" } : info(i.indicador);
  const partes = [NOMBRE_INTENCION[i.intencion], c ? c.nombre : "",
                  (i.territorios || []).join(" y "), (i.anios || []).join("–"),
                  i.causa ? "pregunta por causas" : ""].filter(Boolean);
  r.via_ia = `Interpreté tu pregunta con IA (Gemini) como: ${partes.join(" · ")}. Las cifras provienen de la base de conocimiento, no de la IA.`;
  return r;
}

/* Exponer para el HTML. */
window.Asistente = { cargarKB, responder, responderConIA, detectarIntencion,
                     detectarIndicador, territoriosEn, iaActiva: () => !!IA_URL,
                     _setKB: (k) => { KB = k; } };
})();
