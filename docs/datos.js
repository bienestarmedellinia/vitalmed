/* datos.js — Explorador de datos (módulo independiente del asistente).
 * Lee knowledge_base.json (la misma base que usa el asistente) y muestra TODAS
 * las estadísticas por indicador, territorio y año, con tablas, gráficos y CSV.
 * No usa IA ni se conecta a servicios externos (solo Chart.js desde el CDN).
 */
(function () {
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n, d = 2) => (n === null || n === undefined || Number.isNaN(n)) ? "–"
  : Number(n).toLocaleString("es-CO", { maximumFractionDigits: d });
const corto = (n) => String(n).replace("Corregimiento de ", "Corr. ");
const NAR = "#d9731a", AZUL = "#1f4e79", ROJO = "#c0392b", GRIS = "#6b7280";
const PALETA = ["#d9731a", "#1f4e79", "#2f7d4f", "#8e44ad", "#c0392b", "#16a085"];
const MAX_TERR = 5;

let KB = null, S = null;
const charts = {};
const estado = { ind: null, anio: null, terr: [] };

function grafico(id, cfg) {
  if (typeof Chart === "undefined") return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), cfg);
}
function info(clave) { return S.catalogo.find((c) => c.clave === clave); }
function territorios() {
  return Object.keys(S.territorios).sort((a, b) => a - b).map((c) => ({ cod: c, nombre: S.territorios[c] }));
}
function esSalud(c) { return c.dimension === "salud"; }

/* ── CSV en el navegador (descarga de la vista actual) ──────────────── */
function csv(nombre, cabecera, filas) {
  const celda = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const texto = "\ufeff" + [cabecera, ...filas].map((f) => f.map(celda).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([texto], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = nombre; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
}

/* ── Estado en la URL (#ind=dengue&anio=2016&terr=7,10) ─────────────── */
function leerHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  return { ind: p.get("ind"), anio: Number(p.get("anio")) || null,
           terr: (p.get("terr") || "").split(",").filter(Boolean) };
}
function escribirHash() {
  const p = new URLSearchParams({ ind: estado.ind, anio: String(estado.anio) });
  if (estado.terr.length) p.set("terr", estado.terr.join(","));
  history.replaceState(null, "", "#" + p.toString());
}

/* ── 1. Indicador por territorio ────────────────────────────────────── */
function llenarIndicadores() {
  const dim = $("f-dim").value;
  const lista = S.catalogo.filter((c) => !dim || c.dimension === dim);
  const temas = [...new Set(lista.map((c) => c.tema))].sort();
  $("f-ind").innerHTML = temas.map((t) =>
    `<optgroup label="${esc(t[0].toUpperCase() + t.slice(1))}">` +
    lista.filter((c) => c.tema === t).map((c) =>
      `<option value="${esc(c.clave)}">${esc(c.nombre)}</option>`).join("") +
    "</optgroup>").join("");
  if (!lista.some((c) => c.clave === estado.ind)) estado.ind = lista.length ? lista[0].clave : null;
  $("f-ind").value = estado.ind;
}
function llenarAnios() {
  const c = info(estado.ind);
  if (!c.anios.includes(estado.anio)) estado.anio = c.anios[c.anios.length - 1];
  $("f-anio").innerHTML = [...c.anios].reverse().map((a) => `<option>${a}</option>`).join("");
  $("f-anio").value = String(estado.anio);
}
function valoresAnio(clave, anio) {
  const d = S.datos[clave], a = String(anio);
  return territorios().map((t) => ({ cod: t.cod, nombre: t.nombre,
      valor: (d.valores[t.cod] || {})[a], casos: d.casos ? (d.casos[t.cod] || {})[a] : undefined }))
    .filter((x) => x.valor !== undefined).sort((x, y) => y.valor - x.valor);
}
function mediana(v) {
  const s = [...v].sort((a, b) => a - b), m = Math.floor(s.length / 2);
  return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : null;
}
function pintarIndicador() {
  const c = info(estado.ind), d = S.datos[estado.ind];
  const vals = valoresAnio(estado.ind, estado.anio);
  const ciu = (d.ciudad || {})[String(estado.anio)];
  const med = mediana(vals.map((x) => x.valor));
  const max = vals[0], min = vals[vals.length - 1];
  const tarjetas = [
    [fmt(max && max.valor), `Más alto: ${corto(max ? max.nombre : "–")}`],
    [fmt(min && min.valor), `Más bajo: ${corto(min ? min.nombre : "–")}`],
    [fmt(med), "Mediana de los territorios"],
    [fmt(ciu), "Medellín"],
    [max && min && min.valor ? fmt(max.valor / min.valor, 1) + "×" : "–", "Brecha más alto / más bajo"],
  ];
  $("resumen").innerHTML = tarjetas.map(([n, t]) => `<div class="dato"><div class="n">${n}</div><div class="t">${esc(t)}</div></div>`).join("");

  const sel = estado.terr;
  grafico("c-rank", { type: "bar",
    data: { labels: vals.map((x) => corto(x.nombre)), datasets: [{ label: c.unidad, data: vals.map((x) => x.valor),
      backgroundColor: vals.map((x) => (sel.includes(x.cod) ? NAR : AZUL)) }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false }, title: { display: true, text: `${c.nombre} · ${estado.anio}` },
        tooltip: { callbacks: { label: (t) => `${fmt(t.raw)} ${c.unidad}` } } },
      scales: { x: { title: { display: true, text: c.unidad } } },
      onClick: (e, els) => { if (els.length) alternarTerr(vals[els[0].index].cod); } } });

  const hayCasos = vals.some((x) => x.casos !== undefined && x.casos !== null);
  $("t-rank").innerHTML = `<caption>${esc(c.nombre)} (${esc(c.unidad)}), ${estado.anio}</caption>
    <thead><tr><th scope="col">Territorio</th><th scope="col">Puesto</th><th scope="col">Valor</th>${hayCasos ? '<th scope="col">Casos</th>' : ""}<th scope="col">× mediana</th></tr></thead><tbody>` +
    vals.map((x, i) => `<tr class="${sel.includes(x.cod) ? "sel" : ""}"><td>${esc(x.nombre)}</td><td>${i + 1}</td><td>${fmt(x.valor)}</td>${hayCasos ? `<td>${fmt(x.casos, 0)}</td>` : ""}<td>${med ? fmt(x.valor / med) : "–"}</td></tr>`).join("") +
    (ciu !== undefined ? `<tr class="ciudad"><td>Medellín</td><td></td><td>${fmt(ciu)}</td>${hayCasos ? "<td></td>" : ""}<td>${med ? fmt(ciu / med) : "–"}</td></tr>` : "") + "</tbody>";

  $("lim-ind").textContent = "⚠️ " + (esSalud(c)
    ? `Fuente: ${c.fuente}. Tasas brutas, sin estandarizar por edad. MEData publica estas series por comuna hasta ${c.anios[c.anios.length - 1]}.`
    : `Fuente: ${c.fuente}. Estimación por encuesta: diferencias pequeñas entre territorios pueden no ser significativas.`);
}

/* ── 2. Serie histórica ─────────────────────────────────────────────── */
function llenarTerritorios() {
  $("f-terr").innerHTML = territorios().map((t) =>
    `<label><input type="checkbox" value="${esc(t.cod)}" ${estado.terr.includes(t.cod) ? "checked" : ""}> ${esc(corto(t.nombre))}</label>`).join("");
  $("f-terr").querySelectorAll("input").forEach((i) => i.addEventListener("change", () => alternarTerr(i.value)));
}
function alternarTerr(cod) {
  const i = estado.terr.indexOf(cod);
  if (i >= 0) estado.terr.splice(i, 1);
  else { estado.terr.push(cod); if (estado.terr.length > MAX_TERR) estado.terr.shift(); }
  llenarTerritorios(); pintarIndicador(); pintarSerie(); escribirHash();
}
function pintarSerie() {
  const c = info(estado.ind), d = S.datos[estado.ind], anios = c.anios;
  const series = estado.terr.map((k, i) => ({ label: corto(S.territorios[k]), borderColor: PALETA[i % PALETA.length],
    backgroundColor: PALETA[i % PALETA.length], data: anios.map((a) => (d.valores[k] || {})[String(a)] ?? null) }));
  if (d.ciudad) series.push({ label: "Medellín", borderColor: GRIS, backgroundColor: GRIS, borderDash: [6, 4],
    data: anios.map((a) => d.ciudad[String(a)] ?? null) });
  grafico("c-serie", { type: "line",
    data: { labels: anios.map(String), datasets: series.map((s) => ({ ...s, tension: .25, fill: false, pointRadius: 3, spanGaps: true })) },
    options: { responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { title: { display: true, text: `${c.nombre} · ${anios[0]}–${anios[anios.length - 1]}` },
        subtitle: { display: !estado.terr.length, text: "Marca uno o más territorios para compararlos con Medellín" } },
      scales: { y: { title: { display: true, text: c.unidad } } } } });

  const filas = territorios().map((t) => ({ cod: t.cod, nombre: t.nombre, s: d.valores[t.cod] || {} }));
  $("t-serie").innerHTML = `<caption>${esc(c.nombre)} (${esc(c.unidad)}) por territorio y año</caption>
    <thead><tr><th scope="col">Territorio</th>${anios.map((a) => `<th scope="col">${a}</th>`).join("")}</tr></thead><tbody>` +
    filas.map((f) => `<tr class="${estado.terr.includes(f.cod) ? "sel" : ""}"><td>${esc(f.nombre)}</td>${anios.map((a) => {
      const v = f.s[String(a)]; return v === undefined ? '<td class="vacio">–</td>' : `<td>${fmt(v)}</td>`; }).join("")}</tr>`).join("") +
    (d.ciudad ? `<tr class="ciudad"><td>Medellín</td>${anios.map((a) => `<td>${fmt(d.ciudad[String(a)])}</td>`).join("")}</tr>` : "") + "</tbody>";
}

/* ── 3. Factores asociados ──────────────────────────────────────────── */
function pintarFactores() {
  const res = $("f-res").value, soloSig = $("f-sig").value === "sig";
  const lista = (S.correlaciones || []).filter((x) => x.resultado === res && (!soloSig || x.significativa))
    .sort((a, b) => Math.abs(b.pearson) - Math.abs(a.pearson));
  const nom = (k) => (info(k) || { nombre: k }).nombre;
  grafico("c-fac", { type: "bar",
    data: { labels: lista.map((x) => nom(x.factor).slice(0, 55)), datasets: [{ label: "r de Pearson", data: lista.map((x) => x.pearson),
      backgroundColor: lista.map((x) => (x.significativa ? (x.pearson > 0 ? NAR : AZUL) : "#c7d0db")) }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false }, title: { display: true, text: `Correlación con ${nom(res)} (gris = no apreciable)` } },
      scales: { x: { min: -1, max: 1, title: { display: true, text: "r (−1 a 1)" } } } } });
  $("t-fac").innerHTML = `<caption>Correlación con ${esc(nom(res))} entre territorios</caption>
    <thead><tr><th scope="col">Factor</th><th scope="col">Año</th><th scope="col">n</th><th scope="col">Pearson</th><th scope="col">Spearman</th><th scope="col">Apreciable</th></tr></thead><tbody>` +
    (lista.length ? lista.map((x) => `<tr><td>${esc(nom(x.factor))}</td><td>${x.anio}</td><td>${x.n}</td><td>${fmt(x.pearson, 3)}</td><td>${fmt(x.spearman, 3)}</td><td>${x.significativa ? '<span class="sig">Sí</span>' : "No"}</td></tr>`).join("")
      : '<tr><td colspan="6">Sin correlaciones con este filtro.</td></tr>') + "</tbody>";
  $("lim-fac").textContent = "⚠️ " + (S.nota_correlaciones || "Asociación, no causalidad.");
}

/* ── 4. Aire ─────────────────────────────────────────────────────────── */
function pintarAire() {
  const pm = (KB.indicadores || {}).pm25_siata;
  if (!pm || !pm.serie) { $("aire").style.display = "none"; return; }
  const prom = pm.promedio_estaciones || {}, anios = Object.keys(prom).sort();
  grafico("c-aire", { type: "line",
    data: { labels: anios, datasets: [
      { label: "Promedio de estaciones", data: anios.map((a) => prom[a]), borderColor: NAR, backgroundColor: NAR, tension: .25, pointRadius: 4 },
      { label: "Guía OMS 2021", data: anios.map(() => 5), borderColor: ROJO, borderDash: [6, 4], pointRadius: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { title: { display: true, text: "PM2.5 · promedio anual de estaciones SIATA (µg/m³)" } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "µg/m³" } } } } });
  const est = Object.keys(pm.serie).sort();
  $("t-aire").innerHTML = `<caption>PM2.5 media anual por estación (µg/m³)</caption>
    <thead><tr><th scope="col">Estación</th>${anios.map((a) => `<th scope="col">${a}</th>`).join("")}</tr></thead><tbody>` +
    est.map((e) => `<tr><td>${esc(e)}</td>${anios.map((a) => { const v = pm.serie[e][a]; return v === undefined ? '<td class="vacio">–</td>' : `<td>${fmt(v)}</td>`; }).join("")}</tr>`).join("") +
    `<tr class="ciudad"><td>Promedio</td>${anios.map((a) => `<td>${fmt(prom[a])}</td>`).join("")}</tr></tbody>`;
  $("lim-aire").textContent = "⚠️ " + (pm.advertencia || "") + " " + (pm.criterio || "");
}

/* ── 5. Descargas y diccionario ─────────────────────────────────────── */
async function pintarDescargas() {
  let indice = null;
  try { const r = await fetch("datos/indice.json", { cache: "no-store" }); if (r.ok) indice = await r.json(); } catch (e) { /* sin índice */ }
  const items = (indice ? indice.archivos : []).map((a) =>
    `<li><a href="datos/${esc(a.archivo)}" download>${esc(a.archivo)}</a> — ${esc(a.descripcion)} (${fmt(a.filas, 0)} filas)</li>`);
  items.push('<li><a href="knowledge_base.json" download>knowledge_base.json</a> — base de conocimiento completa (JSON) que usan el explorador y el asistente.</li>');
  $("lista-desc").innerHTML = items.join("");
  $("t-cat").innerHTML = `<caption>Diccionario de indicadores (${S.catalogo.length})</caption>
    <thead><tr><th scope="col">Indicador</th><th scope="col">Clave</th><th scope="col">Unidad</th><th scope="col">Tema</th><th scope="col">Fuente</th><th scope="col">Años</th></tr></thead><tbody>` +
    S.catalogo.map((c) => `<tr><td style="white-space:normal;min-width:260px">${esc(c.nombre)}</td><td>${esc(c.clave)}</td><td>${esc(c.unidad)}</td><td>${esc(c.tema)}</td><td>${esc(c.fuente)}</td><td>${c.anios[0]}–${c.anios[c.anios.length - 1]} (${c.anios.length})</td></tr>`).join("") + "</tbody>";
}

/* ── Descargas de la vista actual ───────────────────────────────────── */
function enlazarDescargas() {
  $("d-rank").onclick = () => {
    const c = info(estado.ind);
    csv(`${estado.ind}_${estado.anio}.csv`, ["territorio", "anio", "valor", "unidad", "casos", "fuente"],
      valoresAnio(estado.ind, estado.anio).map((x) => [x.nombre, estado.anio, x.valor, c.unidad, x.casos ?? "", c.fuente]));
  };
  $("d-serie").onclick = () => {
    const c = info(estado.ind), d = S.datos[estado.ind];
    const filas = [];
    territorios().forEach((t) => c.anios.forEach((a) => {
      const v = (d.valores[t.cod] || {})[String(a)];
      if (v !== undefined) filas.push([t.nombre, a, v, c.unidad]);
    }));
    Object.keys(d.ciudad || {}).forEach((a) => filas.push(["Medellín", a, d.ciudad[a], c.unidad]));
    csv(`${estado.ind}_serie.csv`, ["territorio", "anio", "valor", "unidad"], filas);
  };
  $("d-fac").onclick = () => {
    const nom = (k) => (info(k) || { nombre: k }).nombre;
    csv("factores_asociados.csv", ["resultado", "factor", "anio", "n", "pearson", "spearman", "apreciable"],
      (S.correlaciones || []).map((x) => [nom(x.resultado), nom(x.factor), x.anio, x.n, x.pearson, x.spearman, x.significativa ? "sí" : "no"]));
  };
  $("d-aire").onclick = () => {
    const pm = KB.indicadores.pm25_siata, filas = [];
    Object.keys(pm.serie).sort().forEach((e) => Object.keys(pm.serie[e]).sort().forEach((a) => filas.push([e, a, pm.serie[e][a]])));
    csv("pm25_por_estacion.csv", ["estacion", "anio", "pm25_media_anual_ug_m3"], filas);
  };
  $("copiar").onclick = async () => {
    escribirHash();
    try { await navigator.clipboard.writeText(location.href); $("copiar").textContent = "¡Enlace copiado!"; }
    catch (e) { $("copiar").textContent = "Copia la dirección de la barra del navegador"; }
    setTimeout(() => { $("copiar").textContent = "Copiar enlace a esta vista"; }, 2500);
  };
}

/* ── Arranque ───────────────────────────────────────────────────────── */
async function iniciar() {
  try {
    const r = await fetch("knowledge_base.json", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    KB = await r.json();
  } catch (e) {
    $("estado").textContent = "No se pudo cargar knowledge_base.json: " + e.message;
    return;
  }
  S = KB.series;
  if (!S || !S.catalogo || !S.catalogo.length) {
    $("estado").textContent = "La base de conocimiento no trae series. Ejecuta el pipeline.";
    return;
  }
  const h = leerHash();
  estado.ind = info(h.ind) ? h.ind : (info("mortalidad") ? "mortalidad" : S.catalogo[0].clave);
  estado.anio = h.anio;
  estado.terr = h.terr.filter((k) => S.territorios[k]).slice(0, MAX_TERR);
  if (!estado.terr.length && KB.indicadores && KB.indicadores.hallazgo_mortalidad)
    estado.terr = [String(KB.indicadores.hallazgo_mortalidad.comuna_mayor_tasa.comuna)];

  const sal = S.catalogo.filter(esSalud).length, soc = S.catalogo.length - sal;
  const pmA = Object.keys(((KB.indicadores || {}).pm25_siata || {}).promedio_estaciones || {}).sort();
  $("chips").innerHTML = [`${sal} indicadores de salud (MEData)`, `${soc} indicadores sociales (ECV)`,
    "21 territorios", pmA.length ? `PM2.5 ${pmA[0]}–${pmA[pmA.length - 1]}` : null,
    `${(S.correlaciones || []).length} correlaciones`].filter(Boolean).map((t) => `<span class="chip">${esc(t)}</span>`).join("");

  llenarIndicadores(); llenarAnios(); llenarTerritorios();
  $("f-dim").onchange = () => { llenarIndicadores(); llenarAnios(); pintarIndicador(); pintarSerie(); escribirHash(); };
  $("f-ind").onchange = () => { estado.ind = $("f-ind").value; llenarAnios(); pintarIndicador(); pintarSerie(); escribirHash(); };
  $("f-anio").onchange = () => { estado.anio = Number($("f-anio").value); pintarIndicador(); escribirHash(); };

  const resultados = [...new Set((S.correlaciones || []).map((x) => x.resultado))];
  $("f-res").innerHTML = resultados.map((k) => `<option value="${esc(k)}">${esc((info(k) || { nombre: k }).nombre)}</option>`).join("");
  $("f-res").onchange = pintarFactores; $("f-sig").onchange = pintarFactores;
  if (!resultados.length) $("factores").style.display = "none";

  pintarIndicador(); pintarSerie(); if (resultados.length) pintarFactores(); pintarAire();
  enlazarDescargas(); await pintarDescargas();
  $("estado").textContent = `Datos generados por el pipeline: ${(KB.meta || {}).generado_utc || "?"} UTC.`;
}

window.Explorador = { estado: () => ({ ...estado }) };
iniciar();
})();
