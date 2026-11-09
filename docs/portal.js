/* portal.js — lógica del portal (gráficos, simulador, asistente, flujo).
 * Archivo externo (no inline) para permitir una Content-Security-Policy estricta. */
  "use strict";
  const AZUL = "#1f4e79", NAR = "#d9731a", CIAN = "#5b9bd5", ROJO = "#c0392b", NARO = "#a8540a";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n, d = 1) => Number(n).toLocaleString("es-CO", { maximumFractionDigits: d });
  const corto = (n) => n.replace("Corregimiento de ", "Corr. ");
  const REDUCIR = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const charts = {};
  let T = [];            // territorios unificados
  let ciudad = null;     // tasa global calculada
  let sel = null;        // territorio seleccionado
  let modoMort = "tasa";

  /* ---------- Plugins Chart.js ---------- */
  // Líneas de referencia punteadas: opts.lineas = [{eje, valor, color, texto}]
  const lineasRef = { id: "lineasRef", afterDatasetsDraw(chart, _a, opts) {
    const { ctx, chartArea: ca } = chart;
    (opts.lineas || []).forEach((l) => {
      const sc = chart.scales[l.eje]; if (!sc) return;
      const p = sc.getPixelForValue(l.valor);
      ctx.save(); ctx.strokeStyle = l.color; ctx.fillStyle = l.color; ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]); ctx.beginPath();
      if (l.eje === "x") { ctx.moveTo(p, ca.top); ctx.lineTo(p, ca.bottom); }
      else { ctx.moveTo(ca.left, p); ctx.lineTo(ca.right, p); }
      ctx.stroke(); ctx.setLineDash([]); ctx.font = "12px system-ui"; ctx.textBaseline = "bottom";
      if (l.eje === "x") ctx.fillText(l.texto, Math.min(p + 4, ca.right - ctx.measureText(l.texto).width), ca.bottom - 4);
      else ctx.fillText(l.texto, ca.right - ctx.measureText(l.texto).width - 4, p - 3);
      ctx.restore();
    });
  } };
  // Etiquetas de puntos en dispersión: opts.indices = [i, ...]
  const etiquetas = { id: "etiquetas", afterDatasetsDraw(chart, _a, opts) {
    const { ctx } = chart; const meta = chart.getDatasetMeta(0);
    ctx.save(); ctx.font = "12px system-ui"; ctx.fillStyle = "#1a1a1a";
    (opts.indices || []).forEach((i) => {
      const el = meta.data[i]; if (!el) return;
      const t = corto(T[i].nombre); const w = ctx.measureText(t).width;
      const x = el.x + 8 + w > chart.chartArea.right ? el.x - 8 - w : el.x + 8;
      ctx.fillText(t, x, el.y - 6);
    });
    ctx.restore();
  } };

  function nuevoGrafico(id, cfg) {
    if (typeof Chart === "undefined") return null;
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart($(id), cfg);
    return charts[id];
  }

  /* ---------- Estadística ---------- */
  const mediana = (a) => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  function pearson(x, y) {
    const n = x.length, mx = x.reduce((a, b) => a + b) / n, my = y.reduce((a, b) => a + b) / n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; syy += (y[i] - my) ** 2; }
    return sxy / Math.sqrt(sxx * syy);
  }
  const rangoDe = (arr, key, i) => 1 + arr.filter((t) => t[key] > arr[i][key]).length;

  /* ---------- Unificar territorios ---------- */
  function construirTerritorios(ind) {
    const mort = ((ind.mortalidad_2022 || {}).ranking) || [];
    const ix = ((ind.indice_priorizacion || {}).ranking) || [];
    const porCom = new Map(mort.map((m) => [m.comuna, m]));
    T = ix.map((x, k) => {
      const m = porCom.get(x.comuna) || {};
      return { comuna: x.comuna, nombre: x.nombre, indice: x.indice, nm: x.n_mortalidad, ns: x.n_suicidio,
               tm: x.tasa_mortalidad ?? m.tasa, ts: x.tasa_suicidio, casos: m.casos, rankIdx: k + 1 };
    });
    T.sort((a, b) => b.tm - a.tm);          // orden por mortalidad (como el ranking)
    const casos = T.reduce((s, t) => s + (t.casos || 0), 0);
    const pob = T.reduce((s, t) => s + (t.casos && t.tm ? t.casos / t.tm * 1e5 : 0), 0);
    ciudad = pob ? casos / pob * 1e5 : null;
    T.forEach((t, i, arr) => { t.rm = i + 1; t.rs = rangoDe(arr, "ts", i); });
  }

  /* ---------- Hero y KPIs animados ---------- */
  function contar(el, destino, dec, pref, suf) {
    const fin = () => { el.textContent = pref + fmt(destino, dec) + suf; };
    if (REDUCIR) return fin();
    const t0 = performance.now(), dur = 1200;
    (function paso(t) {
      const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = pref + fmt(destino * e, dec) + suf;
      if (p < 1) requestAnimationFrame(paso); else fin();
    })(t0);
  }
  function pintarHero(KB) {
    const ind = KB.indicadores || {}, h = ind.hallazgo_mortalidad || {}, pm = ind.pm25_siata || {};
    const top = h.comuna_mayor_tasa, bajo = h.comuna_menor_tasa;
    if (!top || !bajo) return;
    $("hero-hallazgo").innerHTML =
      `<h2>Hallazgo principal</h2><p>El bienestar en Medellín es <b>desigual por territorio</b>: la brecha de mortalidad
       llega a <b>${fmt(h.brecha_veces, 2)}×</b> entre ${esc(top.nombre)} y ${esc(bajo.nombre)}, y se repiten patrones
       en empleo, seguridad alimentaria, aire y salud mental.</p>
       <small>Fuentes: MEData, ECV, SIATA, DANE/SIVIGILA/RIPS. Asociación, no causalidad.</small>`;
    const t3 = (((ind.indice_priorizacion || {}).ranking) || []).slice(0, 3).map((x) => x.nombre);
    $("hero-propuesta").innerHTML = t3.length
      ? `<h2>Propuesta de mejora</h2><p>Focalizar <b>intervenciones intersectoriales</b> (empleo, alimentación,
         ambiente y salud física y mental) en los territorios de mayor carga —hoy <b>${esc(t3.join(", "))}</b>—
         y monitorear el avance con estos mismos indicadores.</p><small>Prioridad según el índice de salud; el detalle, en cada pregunta del observatorio.</small>`
      : `<h2>Propuesta de mejora</h2><p>Focalizar intervenciones intersectoriales en los territorios de mayor carga y monitorear su avance.</p>`;
    // KPIs MULTIDIMENSIÓN con CARRUSEL por año (todos los años del KB, sin inventar).
    const S = KB.series || {}, cat = {}, dat = S.datos || {};
    (S.catalogo || []).forEach((c) => (cat[c.clave] = c));
    const serieAnios = (obj) => Object.keys(obj || {}).map(Number).filter((n) => !isNaN(n))
      .sort((a, b) => a - b).map((y) => ({ y: String(y), v: Number(obj[String(y)]) }))
      .filter((p) => !isNaN(p.v));
    const kpis = [];  // {titulo, sub, dec, suf, anios:[{y,v}]}
    const addKPI = (clave, dec, suf, titulo) => {
      const meta = cat[clave]; if (!meta) return;
      const anios = serieAnios((dat[clave] || {}).ciudad);
      if (anios.length) kpis.push({ titulo, dec, suf, anios, unidad: meta.unidad || "", prefijo: "Medellín" });
    };
    // Ambiental: PM2.5 promedio de ciudad por año (2020–2025), más honesto que la estación máx.
    const pmProm = serieAnios(pm.promedio_estaciones);
    if (pmProm.length) kpis.push({ titulo: "PM2.5 (µg/m³)", dec: 1, suf: "", anios: pmProm,
      unidad: "media de estaciones · OMS: 5", prefijo: "Medellín" });
    // Social
    addKPI("ecv_t99", 1, "%", "Desempleo abierto");
    addKPI("ecv_hogares_inseguridad_alimentaria", 1, "%", "Inseguridad alimentaria (hogares)");
    addKPI("ecv_poblacion_practica_actividades_deportivas", 1, "%", "Practica deporte");
    // Salud: mortalidad de ciudad por año (2012–2022)
    const mortAnios = serieAnios((dat.mortalidad || {}).ciudad);
    if (mortAnios.length) kpis.push({ titulo: "Mortalidad (ciudad)", dec: 0, suf: "", anios: mortAnios,
      unidad: "defunciones por 100.000 hab.", prefijo: "Medellín" });
    // Respaldo si no hubo series.
    if (!kpis.length) {
      kpis.push({ titulo: "Mayor tasa de mortalidad", dec: 1, suf: "", prefijo: top.nombre,
        unidad: "por 100.000 hab.", anios: [{ y: String(h.anio_referencia), v: top.tasa }] });
    }
    arrancarCarruselKPIs(kpis);
  }

  /* ---------- Carrusel de KPIs (rota los años de cada tarjeta) ---------- */
  let kpiTimer = null;
  function arrancarCarruselKPIs(kpis) {
    if (kpiTimer) { clearInterval(kpiTimer); kpiTimer = null; }
    $("kpis").innerHTML = kpis.map((x, i) =>
      `<div class="kpi" data-i="${i}">
         <div class="n" id="kn${i}">0</div>
         <div class="t">${esc(x.titulo)}</div>
         <div class="s" id="ks${i}"></div>
         <div class="kpi-anio" id="ka${i}" aria-hidden="true"></div>
       </div>`).join("");
    const idx = kpis.map((x) => x.anios.length - 1);  // arranca en el último año (más reciente)
    const pintar = (i, animar) => {
      const x = kpis[i], p = x.anios[idx[i]];
      $("ks" + i).textContent = `${x.prefijo} · ${x.unidad} · ${p.y}`;
      $("ka" + i).textContent = x.anios.length > 1 ? `${p.y}  (${idx[i] + 1}/${x.anios.length})` : p.y;
      if (animar) contar($("kn" + i), p.v, x.dec, "", x.suf);
      else $("kn" + i).textContent = fmt(p.v, x.dec) + x.suf;
    };
    kpis.forEach((_x, i) => pintar(i, true));
    const multi = kpis.some((x) => x.anios.length > 1);
    if (!multi || REDUCIR) return;  // respeta prefers-reduced-motion y evita rotar si no hay series
    let paso = 0;
    kpiTimer = setInterval(() => {
      paso++;
      // Escalonado: en cada tick avanza una tarjeta distinta (efecto carrusel, no todas a la vez).
      const rotables = kpis.map((x, i) => (x.anios.length > 1 ? i : -1)).filter((i) => i >= 0);
      if (!rotables.length) return;
      const i = rotables[paso % rotables.length];
      idx[i] = (idx[i] + 1) % kpis[i].anios.length;
      pintar(i, false);
    }, 1400);
    // Pausa al pasar el cursor; reanuda al salir.
    const cont = $("kpis");
    cont.onmouseenter = () => { if (kpiTimer) { clearInterval(kpiTimer); kpiTimer = null; } };
    cont.onmouseleave = () => { if (!kpiTimer && multi && !REDUCIR) arrancarCarruselKPIs(kpis); };
  }

  /* ---------- 1. Mortalidad + ficha ---------- */
  const colorBarra = (t) => (t.nombre === sel ? "#7a3a06" : (t.rm <= 3 ? NAR : AZUL));
  function pintarMortalidad() {
    const casos = modoMort === "casos";
    const datos = [...T].sort((a, b) => (casos ? b.casos - a.casos : b.tm - a.tm));
    const cfg = { type: "bar",
      data: { labels: datos.map((t) => t.nombre),
              datasets: [{ data: datos.map((t) => (casos ? t.casos : t.tm)), backgroundColor: datos.map(colorBarra) }] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
        onClick: (_e, els) => { if (els.length) { const n = datos[els[0].index].nombre; setTimeout(() => seleccionar(n), 0); } },
        onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
        plugins: { legend: { display: false },
          lineasRef: { lineas: casos || !ciudad ? [] : [{ eje: "x", valor: ciudad, color: ROJO, texto: `Ciudad: ${fmt(ciudad, 0)}` }] } },
        scales: { x: { title: { display: true, text: casos ? "Defunciones registradas (2022)" : "Defunciones por 100.000 hab. (2022)" } } } },
      plugins: [lineasRef] };
    nuevoGrafico("c-mort", cfg);
  }
  function pintarFicha() {
    const t = T.find((x) => x.nombre === sel); if (!t) return;
    const medM = mediana(T.map((x) => x.tm)), medS = mediana(T.map((x) => x.ts));
    const aM = t.tm > medM, aS = t.ts > medS;
    const [clase, etq] = aM && aS ? ["doble", "Doble carga: sobre la mediana en ambos"]
      : aS ? ["salud", "Alerta de salud mental"] : aM ? ["mort", "Alerta de mortalidad"] : ["bajo", "Bajo la mediana en ambos"];
    const opts = T.map((x) => `<option ${x.nombre === sel ? "selected" : ""}>${esc(x.nombre)}</option>`).join("");
    $("ficha").innerHTML = `
      <label for="sel-terr">Territorio</label>
      <select id="sel-terr">${opts}</select>
      <h3>${esc(t.nombre)}</h3>
      <span class="perfil ${clase}">${etq}</span>
      <div class="dato"><span>Mortalidad (por 100 mil)</span><b>${fmt(t.tm)} · #${t.rm} de ${T.length}</b></div>
      <div class="dato"><span>Respecto a la ciudad</span><b>${ciudad ? fmt(t.tm / ciudad, 2) + "×" : "—"}</b></div>
      <div class="dato"><span>Defunciones 2022</span><b>${fmt(t.casos, 0)}</b></div>
      <div class="dato"><span>Intento de suicidio (por 100 mil)</span><b>${fmt(t.ts)} · #${t.rs} de ${T.length}</b></div>
      <div class="dato"><span>Índice de priorización</span><b>${fmt(t.indice)} · #${t.rankIdx}</b></div>
      <div class="barra-t">Mortalidad normalizada (0–100): ${fmt(t.nm)}</div>
      <div class="barra"><i style="width:${t.nm}%;background:${AZUL}"></i></div>
      <div class="barra-t">Salud mental normalizada (0–100): ${fmt(t.ns)}</div>
      <div class="barra"><i style="width:${t.ns}%;background:${NAR}"></i></div>
      <p class="nota">Fuente: MEData · 2022. La mediana es la de los ${T.length} territorios.</p>`;
    $("sel-terr").onchange = (e) => seleccionar(e.target.value);
  }
  function seleccionar(nombre) {
    sel = nombre; pintarFicha(); pintarMortalidad(); resaltarDisp();
  }

  /* ---------- 2. Dispersión ---------- */
  let medX = 0, medY = 0;
  const idxDoble = () => T.map((t, i) => (t.tm > medX && t.ts > medY ? i : -1)).filter((i) => i >= 0);
  function pintarDispersion() {
    medX = mediana(T.map((t) => t.tm)); medY = mediana(T.map((t) => t.ts));
    const r = pearson(T.map((t) => t.tm), T.map((t) => t.ts));
    const dob = idxDoble().map((i) => T[i].nombre);
    $("disp-insight").innerHTML = `<b>${dob.length}</b> de ${T.length} territorios superan la mediana en ambos indicadores: ${esc(dob.join(", ") || "ninguno")}.
      Correlación de Pearson entre ambos: <b>r = ${fmt(r, 2)}</b> (${Math.abs(r) < 0.3 ? "débil" : Math.abs(r) < 0.6 ? "moderada" : "fuerte"}).
      ${Math.abs(r) < 0.6 ? "Los indicadores se solapan solo en parte: la salud mental aporta información que la mortalidad general no captura." : "Los indicadores se solapan bastante."}`;
    nuevoGrafico("c-disp", { type: "scatter",
      data: { datasets: [{ data: T.map((t) => ({ x: t.tm, y: t.ts })), pointRadius: 7, pointHoverRadius: 10, pointBackgroundColor: [] }] },
      options: { responsive: true, maintainAspectRatio: false,
        onClick: (_e, els) => { if (els.length) { const n = T[els[0].index].nombre; setTimeout(() => seleccionar(n), 0); } },
        onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: (c) => { const t = T[c.dataIndex];
            return [t.nombre, `Mortalidad: ${fmt(t.tm)} /100 mil`, `Intento suicidio: ${fmt(t.ts)} /100 mil`]; } } },
          lineasRef: { lineas: [{ eje: "x", valor: medX, color: "#6b7280", texto: "mediana mortalidad" },
                                { eje: "y", valor: medY, color: "#6b7280", texto: "mediana salud mental" }] },
          etiquetas: { indices: [] } },
        scales: { x: { title: { display: true, text: "Mortalidad general (por 100.000 hab.)" } },
                  y: { title: { display: true, text: "Intento de suicidio (por 100.000 hab.)" } } } },
      plugins: [lineasRef, etiquetas] });
    resaltarDisp();
  }
  function resaltarDisp() {
    const c = charts["c-disp"]; if (!c) return;
    const dob = new Set(idxDoble()), iSel = T.findIndex((t) => t.nombre === sel);
    const ds = c.data.datasets[0];
    ds.pointBackgroundColor = T.map((_, i) => (i === iSel ? "#7a3a06" : dob.has(i) ? ROJO : CIAN));
    ds.pointRadius = T.map((_, i) => (i === iSel ? 11 : 7));
    c.options.plugins.etiquetas.indices = [...new Set([...dob, ...(iSel >= 0 ? [iSel] : [])])];
    c.update("none");
  }

  /* ---------- 3. Simulador y robustez ---------- */
  const indiceCon = (t, w) => (w * t.nm + (100 - w) * t.ns) / 100;
  function pintarSimulador() {
    const w = +$("peso").value;
    const datos = T.map((t) => ({ nombre: t.nombre, v: indiceCon(t, w) })).sort((a, b) => b.v - a.v);
    $("peso-txt").innerHTML = `Mortalidad <b>${w} %</b> · Salud mental <b>${100 - w} %</b> ` +
      (w === 50 ? "(índice base del proyecto)" : "") +
      ` — Top 3 actual: <b>${esc(datos.slice(0, 3).map((d) => d.nombre).join(", "))}</b>`;
    const col = datos.map((_, i) => (i < 3 ? NAR : AZUL));
    let c = charts["c-sim"];
    if (!c) {
      c = nuevoGrafico("c-sim", { type: "bar",
        data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
        options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, animation: { duration: REDUCIR ? 0 : 350 },
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (x) => `Índice: ${fmt(x.parsed.x)}` } } },
          scales: { x: { min: 0, max: 100, title: { display: true, text: "Índice de priorización (0–100)" } } } } });
    }
    if (!c) return;
    c.data.labels = datos.map((d) => d.nombre);
    c.data.datasets[0].data = datos.map((d) => +d.v.toFixed(1));
    c.data.datasets[0].backgroundColor = col;
    c.update();
  }
  function pintarRobustez() {
    const cuenta = new Map(), unos = new Map(); let n = 0;
    for (let w = 0; w <= 100; w += 5) {
      n++;
      const ord = T.map((t) => ({ nombre: t.nombre, v: indiceCon(t, w) })).sort((a, b) => b.v - a.v);
      ord.slice(0, 3).forEach((o) => cuenta.set(o.nombre, (cuenta.get(o.nombre) || 0) + 1));
      unos.set(ord[0].nombre, (unos.get(ord[0].nombre) || 0) + 1);
    }
    const lista = [...cuenta.entries()].sort((a, b) => b[1] - a[1]);
    const primero = [...unos.entries()].sort((a, b) => b[1] - a[1])[0];
    $("rob-insight").innerHTML = `<b>${esc(primero[0])}</b> es el territorio nº 1 en <b>${primero[1]} de ${n}</b> ponderaciones probadas
      (${primero[1] === n ? "la conclusión no depende del peso elegido" : "depende del peso elegido"}). ` +
      `${lista.length} territorios llegan al top 3 en algún escenario.`;
    $("rob-chips").innerHTML = lista.map(([nom, k]) =>
      `<span class="chip ${k === n ? "top" : ""}"><b>${Math.round(k / n * 100)}%</b> ${esc(nom)}</span>`).join("");
  }

  /* ---------- 4/5. Tendencia de ciudad por indicador (multidimensión) ---------- */
  let TEND = null, tendDim = null, tendInd = null, tendBase = false;
  function prepararTendencia(KB) {
    const s = KB.series || {}, cat = s.catalogo || [], datos = s.datos || {};
    const porDim = {};
    cat.forEach((c) => {
      const serie = (datos[c.clave] || {}).ciudad;
      if (!serie || !Object.keys(serie).length) return;
      (porDim[c.dimension] = porDim[c.dimension] || []).push(c);
    });
    return Object.keys(porDim).length ? { cat, datos, porDim } : null;
  }
  function pintarTendInd() {
    if (!TEND || !tendInd) return;
    const meta = TEND.cat.find((c) => c.clave === tendInd) || {};
    const ciudad = (TEND.datos[tendInd] || {}).ciudad || {};
    const anios = Object.keys(ciudad).map(Number).filter((n) => !isNaN(n)).sort((a, b) => a - b);
    const vals0 = anios.map((a) => Number(ciudad[a]));
    const base = tendBase && vals0[0] ? vals0.map((v) => +(v / vals0[0] * 100).toFixed(1)) : vals0;
    const i21 = anios.indexOf(2021);
    $("tend-sub").innerHTML = `<b>${esc(meta.nombre || tendInd)}</b> · ${esc(meta.unidad || "")}
      · ${anios[0]}–${anios[anios.length - 1]} · <small>Fuente: ${esc(meta.fuente || "")}</small>`;
    nuevoGrafico("c-tend", {
      type: "line",
      data: { labels: anios.map(String),
        datasets: [{ data: base, borderColor: NAR, backgroundColor: "rgba(217,115,26,.15)", fill: true, tension: .25,
          pointRadius: anios.map((_, i) => (i === i21 ? 7 : 3)),
          pointBackgroundColor: anios.map((_, i) => (i === i21 ? ROJO : NAR)) }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false },
          lineasRef: { lineas: tendBase ? [{ eje: "y", valor: 100, color: "#6b7280", texto: "base = 100" }] : [] } },
        scales: { y: { title: { display: true, text: tendBase ? "Índice (primer año = 100)" : (meta.unidad || "valor") } } } },
      plugins: [lineasRef] });
  }
  function llenarTendInd() {
    const items = TEND.porDim[tendDim] || [];
    $("tend-ind").innerHTML = items.map((c) => `<option value="${esc(c.clave)}">${esc(c.nombre)}</option>`).join("");
    tendInd = items.length ? items[0].clave : null;
    pintarTendInd();
  }
  function pintarTendencia(KB) {
    TEND = prepararTendencia(KB);
    if (!TEND) { const s = $("tendencia"); if (s) s.style.display = "none"; return; }
    const dims = Object.keys(TEND.porDim).sort((a, b) => TEND.porDim[b].length - TEND.porDim[a].length);
    tendDim = dims[0];
    $("tend-dims").innerHTML = dims.map((d) =>
      `<button type="button" data-d="${esc(d)}" aria-pressed="${d === tendDim}">${esc(DIM_LABEL[d] || d)} (${TEND.porDim[d].length})</button>`).join("");
    $("tend-dims").querySelectorAll("button").forEach((b) => {
      b.onclick = () => { tendDim = b.dataset.d;
        $("tend-dims").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x.dataset.d === tendDim));
        llenarTendInd(); };
    });
    $("tend-ind").onchange = (e) => { tendInd = e.target.value; pintarTendInd(); };
    const alt = (base) => { tendBase = base; $("t-abs").setAttribute("aria-pressed", String(!base)); $("t-base").setAttribute("aria-pressed", String(base)); pintarTendInd(); };
    $("t-abs").onclick = () => alt(false); $("t-base").onclick = () => alt(true);
    llenarTendInd();
  }

  /* ---------- 5. Aire: comparación interanual ---------- */
  function pintarAire(pm) {
    if (!pm || !pm.ranking || !pm.ranking.length) return;
    const cmp = pm.comparacion;
    const est = cmp ? [...cmp.estaciones].sort((a, b) => b.actual - a.actual) : null;
    const OMS = { eje: "y", valor: 5, color: ROJO, texto: "OMS 5 µg/m³" };
    const datasets = est
      ? [{ label: String(cmp.anio_anterior), data: est.map((e) => e.anterior), backgroundColor: "#a9c7e6" },
         { label: String(cmp.anio_actual), data: est.map((e) => e.actual), backgroundColor: AZUL }]
      : [{ label: String(pm.anio), data: pm.ranking.map((x) => x.media_pm25), backgroundColor: AZUL }];
    nuevoGrafico("c-pm", { type: "bar",
      data: { labels: (est || pm.ranking).map((x) => x.estacion), datasets },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: !!est }, lineasRef: { lineas: [OMS] } },
        scales: { y: { beginAtZero: true, title: { display: true, text: "PM2.5 media anual (µg/m³)" } } } },
      plugins: [lineasRef] });
    if (est) {
      const mejor = est.filter((e) => e.actual < e.anterior).length;
      const prom = (k) => est.reduce((s, e) => s + e[k], 0) / est.length;
      const peor = [...est].sort((a, b) => (b.actual - b.anterior) - (a.actual - a.anterior))[0];
      const veces = prom("actual") / 5;
      $("pm-insight").innerHTML = `<b>${mejor} de ${est.length}</b> estaciones mejoraron entre ${cmp.anio_anterior} y ${cmp.anio_actual}.
        El promedio simple de estaciones pasó de <b>${fmt(prom("anterior"))}</b> a <b>${fmt(prom("actual"))} µg/m³</b>,
        aún ${fmt(veces, 1)}× la guía de la OMS.${peor.actual > peor.anterior ? ` Mayor aumento: ${esc(peor.estacion)} (+${fmt(peor.actual - peor.anterior)}).` : ""}`;
    } else {
      $("pm-insight").style.display = "none";
    }
    $("pm-adv").textContent = "⚠️ " + (pm.advertencia || "");
  }

  /* ---------- Asistente (sin cambios de lógica) ---------- */
  const SUGERIDAS = [
    "¿Qué preguntas puedo hacer?",
    "¿Cuál es el hallazgo principal?",
    "¿Qué factores se asocian a la mortalidad?",
    "¿Cómo varió la mortalidad entre 2012 y 2022?",
    "¿Cómo evolucionó el dengue en Robledo?",
    "¿Dónde hay más inseguridad alimentaria?",
    "Si hay presupuesto para 3 territorios, ¿cuáles priorizar?",
    "¿Cómo ha cambiado el aire desde 2020?",
    "¿De dónde provienen los datos del proyecto?",
  ];
  let enCurso = false;
  // soloMotor=true para preguntas sugeridas: respuesta determinista instantánea.
  async function preguntar(soloMotor) {
    const q = $("q").value.trim(); if (!q || enCurso) return;
    const div = $("resp"), btn = $("btn-preguntar");
    $("q").value = "";
    div.style.display = "block";
    const usarIA = soloMotor !== true && window.Asistente.iaActiva();
    if (usarIA) div.innerHTML = `<h3>Respuesta</h3><p class="aviso">Interpretando tu pregunta…</p>`;
    enCurso = true; btn.disabled = true;
    let r;
    try { r = usarIA ? await window.Asistente.responderConIA(q) : window.Asistente.responder(q); }
    finally { enCurso = false; btn.disabled = false; }
    let html = `<h3>Respuesta</h3><p class="nota">Tu pregunta: «${esc(q)}»</p><div class="directa">${esc(r.respuesta_directa)}</div>`;
    if (r.via_ia) html += `<p class="nota">🤖 ${esc(r.via_ia)}</p>`;
    if (!r.encontrado) html += `<p class="aviso">No encontré cifras para esa pregunta. Escribe «¿Qué preguntas puedo hacer?» para ver ejemplos.</p>`;
    if (r.evidencia && r.evidencia.length) {
      html += `<div class="bloque"><b>Evidencia</b><table><tr><th>Indicador</th><th>Valor</th><th>Año</th><th>Territorio</th><th>Fuente</th></tr>`;
      r.evidencia.forEach((e) => { html += `<tr><td>${esc(e.indicador)}</td><td>${esc(e.valor)}</td><td>${esc(e.anio ?? "")}</td><td>${esc(e.territorio ?? "")}</td><td>${esc(e.fuente ?? "")}</td></tr>`; });
      html += `</table></div>`;
    }
    if (r.interpretacion) html += `<div class="bloque"><b>Interpretación:</b> ${esc(r.interpretacion)}</div>`;
    if (r.recomendacion) html += `<div class="bloque"><b>Recomendación:</b> ${esc(r.recomendacion)}</div>`;
    if (r.grafico) html += `<div class="bloque"><div style="position:relative;height:${r.grafico.tipo === "line" ? 300 : 520}px"><canvas id="chart" role="img" aria-label="${esc(r.grafico.titulo)}"></canvas></div></div>`;
    if (r.limitaciones) html += `<div class="limit">⚠️ Limitaciones: ${esc(r.limitaciones)}</div>`;
    div.innerHTML = html;
    if (r.grafico) dibujarGrafico(r.grafico);
  }
  function dibujarGrafico(g) {
    const esLinea = g.tipo === "line", COLORES = [NAR, AZUL, "#2f7d4f"];
    let datasets;
    if (esLinea && g.series && g.series.length) {
      datasets = g.series.map((s, i) => ({ label: s.nombre, data: s.valores, borderColor: COLORES[i % 3],
        backgroundColor: COLORES[i % 3], tension: .25, fill: false, pointRadius: 3, spanGaps: true,
        borderDash: i === g.series.length - 1 && /Medellín/.test(s.nombre) && g.series.length > 1 ? [6, 4] : [] }));
    } else {
      const ds = { label: g.etiqueta_eje, data: g.valores };
      if (esLinea) Object.assign(ds, { borderColor: NAR, backgroundColor: NAR, tension: .25, fill: false, pointRadius: 4 });
      else ds.backgroundColor = g.resaltar.map((on) => (on ? NAR : AZUL));
      datasets = [ds];
    }
    nuevoGrafico("chart", { type: g.tipo, data: { labels: g.labels, datasets: datasets },
      options: { indexAxis: esLinea ? "x" : "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: datasets.length > 1 }, title: { display: true, text: g.titulo } },
        scales: esLinea ? { y: { title: { display: true, text: g.etiqueta_eje } } } : { x: { title: { display: true, text: g.etiqueta_eje } } } } });
  }
  // (El asistente de preguntas libres se retiró del portal: el observatorio por preguntas lo absorbe.
  //  La función preguntar() y SUGERIDAS quedan definidas por si se reactiva, pero no se enlazan a UI.)

  /* ---------- Revelado al hacer scroll ---------- */
  /* ---------- Panorama multidimensional (KB.series) ---------- */
  const DIM_LABEL = { social: "Social y territorial", salud: "Salud", ambiental: "Ambiental" };
  let PAN = null, panDim = null, panInd = null;
  function prepararPanorama(KB) {
    const s = KB.series || {}, cat = s.catalogo || [], datos = s.datos || {};
    if (!cat.length) return null;
    const terr = s.territorios || {};  // {codigo: nombre}
    const porDim = {};
    cat.forEach((c) => {
      const d = datos[c.clave];
      if (!d || !d.valores) return;  // solo indicadores con valores por territorio
      (porDim[c.dimension] = porDim[c.dimension] || []).push(c);
    });
    return { cat, datos, porDim, terr };
  }
  function ultimoAnioDesde(valores) {
    const anios = new Set();
    Object.values(valores).forEach((serie) =>
      Object.keys(serie).forEach((a) => anios.add(Number(a))));
    const arr = [...anios].filter((n) => !isNaN(n));
    return arr.length ? String(Math.max(...arr)) : null;
  }
  function pintarPanorama() {
    if (!PAN || !panDim || !panInd) return;
    const meta = PAN.cat.find((c) => c.clave === panInd) || {};
    const valores = (PAN.datos[panInd] || {}).valores || {};
    const anio = ultimoAnioDesde(valores);
    const filas = Object.entries(valores)
      .map(([cod, serie]) => ({ nombre: PAN.terr[cod] || cod, v: Number(serie[anio]) }))
      .filter((x) => !isNaN(x.v))
      .sort((a, b) => b.v - a.v);
    $("pan-meta").innerHTML = `<b>${esc(meta.nombre || panInd)}</b> · ${esc(meta.unidad || "")} · ${anio || "s/d"}
      · <small>Fuente: ${esc(meta.fuente || "")}</small>`;
    $("pan-nota").textContent = (meta.tema ? "Tema: " + meta.tema + ". " : "")
      + "Comparación entre territorios; asociación, no causalidad.";
    nuevoGrafico("c-pan", {
      type: "bar",
      data: {
        labels: filas.map((f) => corto(f.nombre)),
        datasets: [{ data: filas.map((f) => f.v),
          backgroundColor: filas.map((_f, i) => (i < 3 ? NAR : AZUL)) }],
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });
  }
  function llenarIndicadores() {
    const items = (PAN.porDim[panDim] || []);
    $("pan-ind").innerHTML = items.map((c) =>
      `<option value="${esc(c.clave)}">${esc(c.nombre)}</option>`).join("");
    panInd = items.length ? items[0].clave : null;
    pintarPanorama();
  }
  function iniciarPanorama(KB) {
    PAN = prepararPanorama(KB);
    if (!PAN || !Object.keys(PAN.porDim).length) {
      const s = $("panorama"); if (s) s.style.display = "none"; return;
    }
    const dims = Object.keys(PAN.porDim)
      .sort((a, b) => (PAN.porDim[b].length - PAN.porDim[a].length));
    panDim = dims[0];
    $("pan-dims").innerHTML = dims.map((d) =>
      `<button type="button" data-d="${esc(d)}" aria-pressed="${d === panDim}">${esc(DIM_LABEL[d] || d)} (${PAN.porDim[d].length})</button>`).join("");
    $("pan-dims").querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        panDim = b.dataset.d;
        $("pan-dims").querySelectorAll("button").forEach((x) =>
          x.setAttribute("aria-pressed", x.dataset.d === panDim));
        llenarIndicadores();
      };
    });
    $("pan-ind").onchange = (e) => { panInd = e.target.value; pintarPanorama(); };
    llenarIndicadores();
  }

  /* ---------- 7. Salud en el tiempo (DANE / SIVIGILA / RIPS) ---------- */
  function seriesSalud(ind) {
    const out = [];
    const dane = ind.mortalidad_dane;
    if (dane && dane.serie && dane.serie.respiratorias) {
      out.push({ id: "dane_resp", etiqueta: "Mortalidad respiratoria (mensual, DANE)",
        tipo: "mensual", fuente: "DANE · Estadísticas Vitales",
        unidad: "defunciones/mes (J00-J99)", data: dane.serie.respiratorias,
        nota: dane.advertencia || "" });
    }
    const sv = ind.sivigila;
    if (sv && sv.serie) {
      Object.entries(sv.serie).forEach(([ev, serie]) => {
        out.push({ id: "sivi_" + ev, etiqueta: ev + " (semanal, SIVIGILA)",
          tipo: "semanal", fuente: "INS · SIVIGILA", unidad: "casos/semana",
          data: serie, nota: sv.advertencia || "" });
      });
    }
    const rp = ind.rips;
    if (rp && rp.serie) {
      Object.entries(rp.serie).forEach(([g, serie]) => {
        out.push({ id: "rips_" + g, etiqueta: g + " (anual, RIPS)",
          tipo: "anual", fuente: "MinSalud · RIPS", unidad: "atenciones/año",
          data: serie, nota: rp.advertencia || "" });
      });
    }
    return out;
  }
  function puntosSerie(s) {
    // mensual/semanal: {anio:{periodo:valor}} → etiqueta "anio-periodo"; anual: {anio:valor}
    const pts = [];
    if (s.tipo === "anual") {
      Object.keys(s.data).map(Number).sort((a, b) => a - b).forEach((a) =>
        pts.push({ x: String(a), y: Number(s.data[a]) }));
    } else {
      Object.keys(s.data).map(Number).sort((a, b) => a - b).forEach((a) => {
        const sub = s.data[a];
        Object.keys(sub).map(Number).sort((x, y) => x - y).forEach((p) =>
          pts.push({ x: `${a}-${String(p).padStart(2, "0")}`, y: Number(sub[p]) }));
      });
    }
    return pts;
  }
  let SALUD = null, saludSel = null;
  function pintarSaludTiempo() {
    const s = SALUD.find((x) => x.id === saludSel); if (!s) return;
    const pts = puntosSerie(s);
    $("st-nota").textContent = s.nota;
    $("st-fuente").innerHTML = `<h3>${esc(s.etiqueta)}</h3>
      <p><b>Fuente:</b> ${esc(s.fuente)}<br><b>Unidad:</b> ${esc(s.unidad)}<br>
      <b>Periodicidad:</b> ${esc(s.tipo)}<br><b>Nivel:</b> municipio (Medellín), no comuna.</p>
      <p class="nota">${esc(s.nota)}</p>`;
    nuevoGrafico("c-salud-tiempo", {
      type: "line",
      data: { labels: pts.map((p) => p.x),
        datasets: [{ data: pts.map((p) => p.y), borderColor: AZUL, backgroundColor: AZUL,
          pointRadius: s.tipo === "semanal" ? 0 : 2, borderWidth: 1.5, tension: 0.2 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { ticks: { maxTicksLimit: 12, autoSkip: true } }, y: { beginAtZero: true } },
      },
    });
  }
  function iniciarSaludTiempo(ind) {
    SALUD = seriesSalud(ind);
    if (!SALUD.length) { const s = $("salud-tiempo"); if (s) s.style.display = "none"; return; }
    saludSel = SALUD[0].id;
    $("st-series").innerHTML = SALUD.map((s) =>
      `<button type="button" data-id="${esc(s.id)}" aria-pressed="${s.id === saludSel}">${esc(s.etiqueta)}</button>`).join("");
    $("st-series").querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        saludSel = b.dataset.id;
        $("st-series").querySelectorAll("button").forEach((x) =>
          x.setAttribute("aria-pressed", x.dataset.id === saludSel));
        pintarSaludTiempo();
      };
    });
    pintarSaludTiempo();
  }

  /* ---------- Observatorio por preguntas (banco de 200 → modal con datos reales) ---------- */
  const CAT_ICONO = {
    empleo: "💼", seguridad_alimentaria: "🍲", bienestar: "🌿", calidad_aire: "🌫️",
    salud_fisica: "🩺", salud_mental: "🧠", mortalidad: "📉", enfermedades_transmisibles: "🦠",
    salud_sexual: "👪", cultura: "🎭", violencia_genero: "⚖️", demografia: "🧮", deporte: "🏃",
  };
  let PREGS = null;      // {categorias:[...]}
  let catSel = null;     // id de categoría abierta
  let ultimoFoco = null; // para restaurar foco al cerrar el modal

  function iniciarPreguntas() {
    const cont = $("preg-cats"), panel = $("preg-panel");
    if (!cont || !panel) return;
    fetch("preguntas.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then((data) => {
        PREGS = data;
        const cats = data.categorias || [];
        if (!cats.length) { const s = $("preguntas"); if (s) s.style.display = "none"; return; }
        pintarCategorias(cats);
        prepararModal();
      })
      .catch((err) => { const s = $("preguntas"); if (s) s.style.display = "none"; console.error("preguntas.json:", err); });
  }

  function pintarCategorias(cats) {
    const cont = $("preg-cats");
    // agrupar por 'grupo' preservando el orden de aparición
    const grupos = [];
    cats.forEach((c) => { if (!grupos.includes(c.grupo || "Otras")) grupos.push(c.grupo || "Otras"); });
    cont.innerHTML = grupos.map((g) => {
      const items = cats.filter((c) => (c.grupo || "Otras") === g);
      return `<div class="preg-grupo"><h3>${esc(g)}</h3><div class="cat-grid">` +
        items.map((c) => {
          const n = (c.preguntas || []).length;
          return `<button type="button" class="cat-card" data-id="${esc(c.id)}" aria-expanded="false" aria-controls="preg-panel">
            <span class="ico" aria-hidden="true">${CAT_ICONO[c.id] || "📊"}</span>
            <span class="cn">${esc(c.nombre)}</span>
            <span class="cnum">${n} <span>preguntas</span></span>
          </button>`;
        }).join("") + `</div></div>`;
    }).join("");
    cont.querySelectorAll(".cat-card").forEach((b) => {
      b.onclick = () => abrirCategoria(b.dataset.id);
    });
  }

  function abrirCategoria(id) {
    catSel = id;
    const cat = (PREGS.categorias || []).find((c) => c.id === id);
    $("preg-cats").querySelectorAll(".cat-card").forEach((b) =>
      b.setAttribute("aria-expanded", b.dataset.id === id));
    const panel = $("preg-panel");
    if (!cat) { panel.innerHTML = ""; return; }
    panel.innerHTML = panelCategoria(cat) +
      `<div class="preg-panel-head"><h3>Preguntas de ${esc(cat.nombre)} · ${(cat.preguntas || []).length}</h3></div>
      <div class="preg-lista">` +
      (cat.preguntas || []).map((p, i) =>
        `<button type="button" class="preg-card" data-idx="${i}">
           <span class="q">${esc(p.q)}${p.multitema ? '<span class="mt">multitema</span>' : ""}</span>
           <span class="meta">${esc(p.tipo || "")}${(p.indicadores || []).length ? " · " + esc(p.indicadores.join(", ")) : ""}</span>
           <span class="ver">Ver la respuesta →</span>
         </button>`).join("") + `</div>`;
    panel.querySelectorAll(".preg-card").forEach((b) => {
      b.onclick = () => abrirModal(cat, cat.preguntas[+b.dataset.idx], b);
    });
    panel.scrollIntoView({ behavior: REDUCIR ? "auto" : "smooth", block: "nearest" });
  }

  /* ----- Panel de categoría: 5 módulos estándar desde datos reales del KB ----- */
  // Analiza una serie de ciudad {anio:valor} → {actual, anio, prev, varPct, tendencia}
  function analizarSerie(obj) {
    const anios = Object.keys(obj || {}).map(Number).filter((n) => !isNaN(n)).sort((a, b) => a - b);
    if (!anios.length) return null;
    const a1 = anios[anios.length - 1], a0 = anios.length > 1 ? anios[anios.length - 2] : null;
    const v1 = Number(obj[a1]), v0 = a0 != null ? Number(obj[a0]) : null;
    const varPct = (v0 != null && v0 !== 0) ? (v1 - v0) / Math.abs(v0) * 100 : null;
    // tendencia: pendiente del primer al último año (signo)
    const vIni = Number(obj[anios[0]]);
    const dir = v1 - vIni;
    let tendencia = "estable";
    if (Math.abs(dir) > Math.abs(vIni) * 0.02) tendencia = dir > 0 ? "sube" : "baja";
    return { actual: v1, anio: a1, prev: v0, varPct, tendencia, nAnios: anios.length };
  }
  // ¿subir es bueno o malo? Para semáforo por tendencia. true = subir es MALO (rojo si sube).
  function subirEsMalo(clave) {
    const malos = ["mortalidad", "intento_suicidio", "dengue", "hepatitis_a", "parotiditis", "tosferina",
      "tuberculosis_pulmonar", "varicela", "violencia_genero", "pm25_siata", "mortalidad_dane", "sivigila", "rips"];
    if (malos.includes(clave)) return true;
    if (clave.indexOf("inseguridad") >= 0 || clave.indexOf("desempleo") >= 0 || clave === "ecv_t44") return true;
    return false;  // empleo/ocupación/deporte/cultura/planificación: subir es bueno
  }
  // Dispersión entre los 21 territorios en el último año con dato →
  // {anio, min, max, brecha, nombreMax, nombreMin, n}
  function dispersionTerritorial(clave) {
    const S = (KBG || {}).series || {}; const dat = S.datos || {}; const terr = S.territorios || {};
    const vals = (dat[clave] || {}).valores; if (!vals) return null;
    let anio = null;
    Object.values(vals).forEach((serie) => Object.keys(serie || {}).forEach((a) => {
      const n = Number(a); if (!isNaN(n) && (anio == null || n > anio)) anio = n;
    }));
    if (anio == null) return null;
    const puntos = [];
    Object.keys(vals).forEach((cod) => {
      const v = Number((vals[cod] || {})[String(anio)]);
      if (!isNaN(v)) puntos.push({ v, nombre: terr[cod] || ("Territorio " + cod) });
    });
    if (puntos.length < 2) return null;
    puntos.sort((a, b) => a.v - b.v);
    const min = puntos[0], max = puntos[puntos.length - 1];
    const brecha = (min.v > 0) ? max.v / min.v : null;
    return { anio, min: min.v, max: max.v, nombreMin: min.nombre, nombreMax: max.nombre, brecha, n: puntos.length };
  }
  function panelCategoria(cat) {
    const KB = KBG || {}; const S = KB.series || {}; const dat = S.datos || {}; const catl = S.catalogo || [];
    const metaDe = (cl) => catl.find((c) => c.clave === cl) || {};
    const claves = [...new Set((cat.preguntas || []).map((p) => p.clave).filter((c) => (dat[c] || {}).ciudad))];
    // Claves "propias" de la categoría = aparecen en alguna pregunta NO multitema (no entran solo de refilón).
    const clavesPropias = new Set((cat.preguntas || []).filter((p) => !p.multitema && p.clave).map((p) => p.clave));
    // Módulo 2: indicadores clave con semáforo por tendencia
    const filas = claves.map((cl) => {
      const an = analizarSerie((dat[cl] || {}).ciudad); if (!an) return null;
      const malo = subirEsMalo(cl);
      const bueno = an.tendencia === "estable" ? "amb" : ((an.tendencia === "sube") === malo ? "mal" : "bien");
      const semaforo = an.tendencia === "estable" ? "🟡" : (bueno === "bien" ? "🟢" : "🔴");
      return { clave: cl, nombre: (metaDe(cl).nombre || cl), unidad: metaDe(cl).unidad || "", an, semaforo, bueno };
    }).filter(Boolean);
    // Módulo 1: resumen ejecutivo (narrativa a partir de lo anterior)
    const empeoran = filas.filter((f) => f.bueno === "mal").map((f) => f.nombre);
    const mejoran = filas.filter((f) => f.bueno === "bien").map((f) => f.nombre);
    let resumen = `En <b>${esc(cat.nombre)}</b> se analizan ${filas.length || (cat.preguntas || []).length} indicador(es) con datos reales del pipeline. `;
    if (mejoran.length) resumen += `Mejoran: <b>${esc(mejoran.slice(0, 3).join(", "))}</b>. `;
    if (empeoran.length) resumen += `Requieren atención (tendencia desfavorable): <b>${esc(empeoran.slice(0, 3).join(", "))}</b>. `;
    resumen += `La evidencia es a nivel de ${cat.grupo === "Ambientales" ? "estación/ciudad" : "territorio"}; asociación, no causalidad.`;
    // Módulo 5: priorización territorial (usa el índice global de salud como proxy transversal)
    const ix = ((KB.indicadores || {}).indice_priorizacion || {}).ranking || [];
    const criticos = ix.slice(0, 5).map((x) => x.nombre);
    const resilientes = ix.slice(-3).map((x) => x.nombre).reverse();
    // Módulo 6: hallazgos IA (correlaciones del KB que tocan alguna clave de la categoría)
    const corr = S.correlaciones || [];
    const setCat = new Set(claves.concat((cat.preguntas || []).map((p) => p.clave)));
    const hall = (Array.isArray(corr) ? corr : []).filter((c) =>
      c && (setCat.has(c.resultado) || setCat.has(c.factor)) && (c.significativa || Math.abs(c.pearson || 0) >= 0.5))
      .slice(0, 3).map((c) => {
        const na = metaDe(c.resultado).nombre || c.resultado, nb = metaDe(c.factor).nombre || c.factor;
        const signo = (c.pearson || 0) >= 0 ? "acompaña (misma dirección)" : "es inversa";
        return `Entre los 21 territorios, <b>${esc(na)}</b> y <b>${esc(nb)}</b>: la relación ${signo} (r=${fmt(c.pearson, 2)}).`;
      });

    const modIndicadores = filas.length ? `
      <h4>Indicadores clave (último año · variación · tendencia)</h4>
      <div class="tabla-wrap"><table class="m-kpis"><thead><tr><th>Indicador</th><th>Valor</th><th>Variación anual</th><th>Tendencia</th></tr></thead>
      <tbody>${filas.map((f) => `<tr><td>${esc(f.nombre)}</td>
        <td>${fmt(f.an.actual, 1)}${f.unidad && f.unidad.indexOf("%") >= 0 ? "%" : ""} <small>(${f.an.anio})</small></td>
        <td>${f.an.varPct == null ? "—" : (f.an.varPct >= 0 ? "+" : "") + fmt(f.an.varPct, 1) + "%"}</td>
        <td>${f.semaforo} ${f.an.tendencia === "sube" ? "sube" : f.an.tendencia === "baja" ? "baja" : "estable"}</td></tr>`).join("")}</tbody></table></div>
      <p class="nota">Semáforo por <b>tendencia</b> (🟢 evoluciona a favor · 🔴 en contra · 🟡 estable), no contra una meta (el proyecto no tiene metas oficiales).</p>` : "";

    /* ----- Módulo: ANÁLISIS TÉCNICO (síntesis cuantitativa por categoría, 100 % derivada del KB) ----- */
    // Helpers de redacción (texto natural, todo derivado del KB; sin inventar cifras).
    const unidadSuf = (cl) => ((metaDe(cl).unidad || "").indexOf("%") >= 0 ? "%" : "");
    const tendVerbo = (t) => (t === "sube" ? "ascendente" : t === "baja" ? "descendente" : "estable");
    const tendGerundio = (t) => (t === "sube" ? "aumentar" : t === "baja" ? "disminuir" : "mantenerse estable");

    // (b) Relaciones: correlaciones que tocan la categoría (contexto estadístico).
    const corrCat = (Array.isArray(corr) ? corr : []).filter((c) =>
      c && (setCat.has(c.resultado) || setCat.has(c.factor)));
    const corrSig = corrCat.filter((c) => c.significativa);
    // (c) Fuentes y cobertura reales de los indicadores de la categoría.
    const fuentes = [...new Set(claves.map((cl) => metaDe(cl).fuente).filter(Boolean))];
    const anios = claves.map((cl) => (metaDe(cl).anios || [])).filter((a) => a.length);
    const aMin = anios.length ? Math.min(...anios.map((a) => a[0])) : null;
    const aMax = anios.length ? Math.max(...anios.map((a) => a[a.length - 1])) : null;
    const nivel = cat.grupo === "Ambientales" ? "estación de monitoreo (no comuna)"
      : (claves.length ? "21 territorios (16 comunas y 5 corregimientos)" : "ciudad");

    /* ===== ANÁLISIS TÉCNICO (estructura narrativa, 100 % derivada del KB) ===== */
    // (d) Descripción del indicador.
    const dims = [...new Set(claves.map((cl) => metaDe(cl).dimension).filter(Boolean))];
    const unidades = [...new Set(claves.map((cl) => metaDe(cl).unidad).filter(Boolean))];
    const interpPorClave = {};
    (cat.preguntas || []).forEach((p) => { if (p.clave && p.interpretacion && !interpPorClave[p.clave]) interpPorClave[p.clave] = p.interpretacion; });
    const nombresInd = claves.map((cl) => metaDe(cl).nombre || cl);
    // Descripciones curadas por indicador (docs/descripciones.json); si existen, se priorizan.
    const curadas = claves.map((cl) => (DESCG || {})[cl]).filter(Boolean);
    let descripcion;
    if (curadas.length) {
      descripcion = curadas.join(" ");
      // si quedan indicadores sin descripción curada, se completa con el genérico
      const sinCurar = claves.filter((cl) => !(DESCG || {})[cl]).map((cl) => metaDe(cl).nombre || cl);
      if (sinCurar.length) descripcion += ` La categoría incluye además: ${esc(sinCurar.join(", "))}.`;
    } else {
      descripcion = `La categoría <b>${esc(cat.nombre)}</b> agrupa <b>${claves.length || (cat.preguntas || []).length}</b> indicador(es)`;
      if (nombresInd.length) descripcion += ` (${esc(nombresInd.slice(0, 4).join(", "))}${nombresInd.length > 4 ? ", entre otros" : ""})`;
      if (dims.length) descripcion += ` de la dimensión <b>${esc(dims.join(", "))}</b>`;
      descripcion += ". ";
      const primeraInterp = claves.map((cl) => interpPorClave[cl]).find(Boolean);
      if (primeraInterp) descripcion += esc(primeraInterp) + " ";
      if (unidades.length) descripcion += `Unidad de medida: ${esc(unidades.join("; "))}.`;
    }

    // (e) Comportamiento histórico: un párrafo por indicador con serie de ciudad.
    const parrafosHist = claves.map((cl) => {
      const serieCiudad = (dat[cl] || {}).ciudad || {};
      const an = analizarSerie(serieCiudad); if (!an) return null;
      const aniosSerie = Object.keys(serieCiudad).map(Number).filter((n) => !isNaN(n)).sort((a, b) => a - b);
      const a0 = aniosSerie.length ? aniosSerie[0] : null, a1 = aniosSerie.length ? aniosSerie[aniosSerie.length - 1] : an.anio;
      const nombre = metaDe(cl).nombre || cl, suf = unidadSuf(cl);
      let t = `<b>${esc(nombre)}</b>. `;
      if (an.nAnios > 2 && a0 != null) {
        t += `Durante el período ${a0}–${a1}, el indicador evidencia una tendencia estructural `;
        t += an.tendencia === "estable" ? "de estabilidad" : (an.tendencia === "sube" ? "de aumento" : "de disminución");
        t += " en la ciudad. ";
      }
      t += `El último dato disponible para la ciudad corresponde a <b>${fmt(an.actual, 1)}${suf}</b> en ${an.anio}`;
      if (an.varPct != null) {
        const dir = an.varPct >= 0 ? "un aumento" : "una disminución";
        t += `, registrando ${dir} interanual de ${fmt(Math.abs(an.varPct), 1)}% frente al año inmediatamente anterior`;
      }
      t += ". ";
      if (an.nAnios > 2 && an.tendencia !== "estable") {
        t += `El análisis de la serie histórica muestra que ${an.tendencia === "baja" ? "la reducción" : "el aumento"} no corresponde a una fluctuación aislada, sino a una trayectoria sostenida observada a lo largo de los últimos ${an.nAnios} años. `;
      }
      const ctx = (CTXG || {})[cl];
      if (ctx) t += esc(ctx) + " ";
      return `<p>${t}</p>`;
    }).filter(Boolean);
    // Nota genérica de cierre: recuerda que las hipótesis no son relaciones comprobadas.
    const histContexto = `<p class="nota">Las asociaciones mencionadas se presentan como hipótesis de contexto, no como relaciones comprobadas; pueden influir factores no medidos en esta serie (condiciones económicas de los hogares, oferta institucional, dinámicas demográficas o efectos posteriores a la pandemia 2020-2021).</p>`;

    // (f) Análisis territorial: dispersión máx/mín con nombres + brecha, por indicador.
    const parrafosTerr = claves.map((cl) => {
      const disp = dispersionTerritorial(cl); if (!disp) return null;
      const nombre = metaDe(cl).nombre || cl, suf = unidadSuf(cl);
      const ap = (TAPG || {})[cl];
      let t = `<p><b>${esc(nombre)}</b>. La distribución territorial del indicador presenta una alta heterogeneidad entre comunas y corregimientos${ap ? ", " + esc(ap) : ""}. Para ${disp.anio} se observa que:</p>`;
      // Glosa curada del valor: "magnitud|unidad glosada" → enriquece ambas viñetas.
      const gv = (GVALG || {})[cl] || "";
      const [gMag, gUni] = gv.split("|");
      const mag = gMag ? ` ${esc(gMag.trim())}` : "";
      const uni = gUni ? ` ${esc(gUni.trim())}` : "";
      const apenas = (disp.brecha && disp.brecha >= 3) ? "apenas " : "";
      const items = [
        `<b>${esc(disp.nombreMax)}</b> registra el mayor nivel${mag} con ${fmt(disp.max, 1)}${suf}${uni}.`,
        `<b>${esc(disp.nombreMin)}</b> presenta el menor nivel${mag} con ${apenas}${fmt(disp.min, 1)}${suf}${uni}.`,
      ];
      if (disp.brecha && disp.brecha >= 1.05) {
        let b = `La diferencia entre ambos territorios representa una <b>brecha relativa de ${fmt(disp.brecha, 1)} veces</b>`;
        const gb = (GBRG || {})[cl];
        if (gb) b += `, reflejando importantes desigualdades territoriales ${esc(gb)}`;
        else if (disp.brecha >= 2) b += ", lo que refleja desigualdades territoriales relevantes en el acceso a oportunidades o condiciones";
        items.push(b + ".");
      }
      t += `<ul>${items.map((i) => `<li>${i}</li>`).join("")}</ul>`;
      const dh = (DISPG || {})[cl];
      if (dh) t += `<p>${esc(dh)}</p>`;
      return t;
    }).filter(Boolean);
    const terrContexto = parrafosTerr.length
      ? `<p class="nota">La magnitud de la dispersión se interpreta como asociación descriptiva entre territorios, no como causalidad.</p>`
      : (cat.grupo === "Ambientales"
        ? `<p class="nota">Esta categoría se mide por estación de monitoreo (no por comuna), por lo que no se calcula dispersión territorial entre los 21 territorios.</p>` : "");

    // (g) Evaluación de relaciones territoriales.
    // Referencia al indicador: si hay glosa curada de magnitud (p. ej. "de participación cultural"),
    // se nombra el indicador; si no, "de la categoría".
    const gvRef = claves.map((cl) => ((GVALG || {})[cl] || "").split("|")[0]).find((s) => s && s.trim());
    const indRef = gvRef ? `el indicador ${esc(gvRef.trim())}` : "el indicador de la categoría";
    let relaciones;
    if (corrSig.length) {
      const ej = corrSig.slice(0, 3).map((c) => {
        const na = metaDe(c.resultado).nombre || c.resultado, nb = metaDe(c.factor).nombre || c.factor;
        return `${esc(na)} ↔ ${esc(nb)} (r=${fmt(c.pearson, 2)}, ${(c.pearson || 0) >= 0 ? "directa" : "inversa"})`;
      }).join("; ");
      relaciones = `Se evaluaron relaciones entre ${indRef} y otras variables territoriales disponibles para los 21 territorios de Medellín (16 comunas y 5 corregimientos). De ellas, <b>${corrSig.length}</b> alcanzaron significancia estadística (Pearson y Spearman al 95%): ${ej}. Estas asociaciones describen patrones conjuntos entre territorios y deben interpretarse como evidencia descriptiva, no como relaciones de causa-efecto.`;
    } else if (corrCat.length) {
      const cuantas = corrCat.length === 1 ? "una relación" : `${corrCat.length} relaciones`;
      relaciones = `Se analizaron ${cuantas} entre ${indRef} y otras variables territoriales disponibles para los 21 territorios de Medellín (16 comunas y 5 corregimientos). Sin embargo, las asociaciones identificadas no alcanzaron niveles de significancia estadística que permitan establecer patrones consistentes o relaciones robustas. Por tanto, los resultados observados deben interpretarse únicamente como asociaciones descriptivas y no como evidencia de causalidad.`;
    } else {
      relaciones = `El esquema de correlaciones del proyecto se calcula sobre los indicadores de resultado en salud; para esta categoría no se dispone de relaciones territoriales calculadas en el conocimiento base, por lo que el análisis es descriptivo.`;
    }

    // (h) Consideraciones metodológicas.
    const fuentesLeg = fuentes.map((f) => (FLEG || {})[f] || f);
    const fuentesProsa = fuentesLeg.length ? esc(fuentesLeg.join(" y ")) : "las fuentes del pipeline del proyecto";
    const infraMatiz = claves.map((cl) => (INFRAG || {})[cl]).find(Boolean) || "";
    const metodologia = `<p>El análisis se desarrolló utilizando información proveniente de ${fuentesProsa}, considerando los siguientes componentes:</p>
      <ul>
        <li>Cobertura temporal: ${aMin && aMax ? `${aMin}–${aMax}` : "según disponibilidad del indicador"}.</li>
        <li>Cobertura espacial: ${nivel}.</li>
        <li>Evaluación de tendencias mediante comparación entre extremos de la serie.</li>
        <li>Cálculo de variaciones interanuales.</li>
        <li>Medición de dispersión territorial a partir de valores máximos y mínimos.</li>
        <li>Exploración de asociaciones entre indicadores territoriales (Pearson y Spearman).</li>
      </ul>
      <p class="nota">Es importante señalar que el análisis no incorpora controles estadísticos asociados a variables demográficas o socioeconómicas tales como edad, nivel educativo, ingresos del hogar, composición poblacional o disponibilidad de infraestructura${infraMatiz ? " " + esc(infraMatiz) : ""}. En consecuencia, los hallazgos deben entenderse como un análisis descriptivo exploratorio orientado a identificar patrones y desigualdades territoriales.</p>`;

    // (i) Situaciones de atención.
    const situaciones = [];
    filas.forEach((f) => {
      if (f.bueno === "mal") {
        const sube = f.an.tendencia === "sube";
        const titulo = sube ? "Aumento sostenido" : "Reducción sostenida";
        const mag = ((GVALG || {})[f.clave] || "").split("|")[0];
        // En esta viñeta la magnitud lleva artículo: "de participación cultural" → "de la participación cultural".
        const magArt = mag ? mag.trim().replace(/^de\s+/i, "de la ") : "";
        const deQue = magArt ? ` ${esc(magArt)}` : ` en <b>${esc(f.nombre)}</b>`;
        const col = (SREDG || {})[f.clave] || "lo que podría indicar un debilitamiento de las condiciones asociadas al indicador";
        situaciones.push(`${titulo}${deQue} en la ciudad (último dato ${fmt(f.an.actual, 1)}${f.unidad && f.unidad.indexOf("%") >= 0 ? "%" : ""}, ${f.an.anio}), ${esc(col)}.`);
      }
    });
    claves.forEach((cl) => {
      const disp = dispersionTerritorial(cl);
      if (disp && disp.brecha && disp.brecha >= 2) {
        const mag = ((GVALG || {})[cl] || "").split("|")[0];
        const deQue = mag ? ` de ${esc(mag.trim()).replace(/^de /, "")}` : "";
        situaciones.push(`Amplias brechas territoriales, donde algunos sectores presentan niveles${deQue} hasta ${fmt(disp.brecha, 1)} veces superiores a otros (${esc(disp.nombreMax)} frente a ${esc(disp.nombreMin)}).`);
        const act = (ACTG || {})[cl];
        situaciones.push(`Concentración de la actividad${act ? " " + esc(act) : ""} en territorios con mayores condiciones socioeconómicas, sugiriendo posibles barreras de acceso en sectores con menores oportunidades.`);
      }
    });
    if (corrSig.length) situaciones.push(`Presencia de <b>${corrSig.length}</b> asociación(es) estadísticamente significativa(s) entre territorios que merecen seguimiento.`);
    const modSituaciones = situaciones.length ? `<h4 class="subsub">Situaciones de atención</h4><ul>${situaciones.slice(0, 5).map((s) => `<li>${s}</li>`).join("")}</ul>` : "";

    // (j) Implicaciones para la gestión pública: curadas por indicador si existen; si no, acciones del banco.
    const impCuradas = claves.filter((cl) => clavesPropias.has(cl)).flatMap((cl) => ((IMPG || {})[cl] || [])).map((a) => String(a).trim()).filter(Boolean);
    const accionesBanco = [...new Set((cat.preguntas || []).flatMap((p) => p.acciones || []).map((a) => String(a).trim()).filter(Boolean))];
    const implicItems = impCuradas.length ? [...new Set(impCuradas)] : accionesBanco;
    const modImplic = implicItems.length ? `<h4 class="subsub">Implicaciones para la gestión pública</h4>
        <ul>${implicItems.slice(0, 6).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
        <p class="nota">Líneas de acción sugeridas por el patrón observado; no constituyen prescripción.</p>` : "";

    // (k) Conclusión ejecutiva.
    const empeoranN = filas.filter((f) => f.bueno === "mal").length;
    const mejoranN = filas.filter((f) => f.bueno === "bien").length;
    let brechaMaxCl = null, brechaMaxDisp = null;
    claves.forEach((cl) => {
      const d = dispersionTerritorial(cl);
      if (d && d.brecha && (!brechaMaxDisp || d.brecha > brechaMaxDisp.brecha)) { brechaMaxDisp = d; brechaMaxCl = cl; }
    });
    let conclusion = `En <b>${esc(cat.nombre)}</b>, `;
    if (empeoranN && !mejoranN) conclusion += `los indicadores muestran una evolución predominantemente desfavorable`;
    else if (mejoranN && !empeoranN) conclusion += `los indicadores evolucionan de forma predominantemente favorable`;
    else if (empeoranN && mejoranN) conclusion += `el panorama es mixto (${mejoranN} mejora(n), ${empeoranN} requiere(n) atención)`;
    else conclusion += `los indicadores se mantienen relativamente estables`;
    if (aMin && aMax) conclusion += ` en el período ${aMin}–${aMax}`;
    conclusion += `. `;
    if (brechaMaxDisp && brechaMaxDisp.brecha >= 1.5) conclusion += `La mayor desigualdad territorial se observa en <b>${esc(metaDe(brechaMaxCl).nombre || brechaMaxCl)}</b> (brecha ${fmt(brechaMaxDisp.brecha, 1)}×, de ${esc(brechaMaxDisp.nombreMin)} a ${esc(brechaMaxDisp.nombreMax)}). `;
    conclusion += corrSig.length
      ? `Existen asociaciones significativas que orientan la focalización. `
      : `No se identifican relaciones estadísticamente robustas, por lo que los patrones deben leerse como descriptivos. `;
    conclusion += `Se recomienda focalizar esfuerzos en los territorios rezagados para reducir las brechas observadas.`;
    // Si hay conclusión ejecutiva curada para un indicador PROPIO de la categoría, se prioriza.
    const concCurada = claves.filter((cl) => clavesPropias.has(cl)).map((cl) => (CONCG || {})[cl]).find(Boolean);
    if (concCurada) conclusion = esc(concCurada);

    const modAnalisis = (parrafosHist.length || parrafosTerr.length || fuentes.length) ? `
      <div class="cat-mod cat-analisis"><h4>Análisis técnico</h4>
        <h4 class="sub">Descripción del indicador</h4>
        <p>${descripcion}</p>
        ${parrafosHist.length ? `<h4 class="sub">Comportamiento histórico</h4>${parrafosHist.join("")}${histContexto}` : ""}
        ${parrafosTerr.length || terrContexto ? `<h4 class="sub">Análisis territorial</h4>${parrafosTerr.join("")}${terrContexto}` : ""}
        <h4 class="sub">Evaluación de relaciones territoriales</h4>
        <p>${relaciones}</p>
        <h4 class="sub">Consideraciones metodológicas</h4>
        ${metodologia}
        ${(modSituaciones || modImplic) ? `<h4 class="sub">Hallazgos estratégicos</h4>` : ""}
        ${modSituaciones}
        ${modImplic}
        <h4 class="sub">Conclusión ejecutiva</h4>
        <p>${conclusion}</p>
      </div>` : "";

    return `<div class="cat-panel">
      <div class="cat-mod"><h4>Resumen ejecutivo</h4><p>${resumen}</p></div>
      ${modIndicadores}
      ${modAnalisis}
      ${criticos.length ? `<div class="cat-mod"><h4>Priorización territorial (índice de salud)</h4>
        <p><b>Territorios críticos:</b> ${esc(criticos.join(", "))}.<br>
        <b>Mejores desempeños:</b> ${esc(resilientes.join(", "))}.</p></div>` : ""}
      ${hall.length ? `<div class="cat-mod"><h4>Hallazgos automáticos (correlaciones del KB)</h4>
        <ul>${hall.map((h) => `<li>${h}</li>`).join("")}</ul>
        <p class="nota">Correlación entre 21 territorios; describe patrones, no causas.</p></div>` : ""}
    </div>`;
  }

  /* ----- Modal ----- */
  function prepararModal() {
    const ov = $("preg-modal"); if (!ov) return;
    const cerrar = () => cerrarModal();
    $("modal-x").onclick = cerrar;
    ov.addEventListener("click", (e) => { if (e.target === ov) cerrar(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !ov.hidden) cerrar(); });
  }
  function cerrarModal() {
    const ov = $("preg-modal"); if (!ov) return;
    ov.hidden = true;
    if (charts["modal-canvas"]) { charts["modal-canvas"].destroy(); delete charts["modal-canvas"]; }
    if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  }
  function abrirModal(cat, p, origen) {
    const ov = $("preg-modal"); if (!ov || !p) return;
    ultimoFoco = origen || null;
    $("modal-q").textContent = p.q;
    // Badges: tipo · prioridad · indicadores
    const prioClase = { Alta: "b-prio-alta", Media: "b-prio-media", Baja: "b-prio-baja" }[p.prioridad] || "b-prio-media";
    let badges = "";
    if (p.tipo) badges += `<span class="b-tipo">${esc(p.tipo)}</span>`;
    if (p.prioridad) badges += `<span class="${prioClase}">Prioridad ${esc(p.prioridad)}</span>`;
    (p.indicadores || []).forEach((i) => { badges += `<span class="b-ind">${esc(i)}</span>`; });
    $("modal-badges").innerHTML = badges;
    // Ejemplo de respuesta analítica (lectura narrativa; las cifras exactas están en la gráfica/tabla)
    $("modal-resp").innerHTML = p.ejemplo ? `<b>Lectura:</b> ${esc(p.ejemplo)}` : "";
    $("modal-resp").style.display = p.ejemplo ? "" : "none";
    // Interpretación técnica
    $("modal-interp").textContent = p.interpretacion || "";
    $("modal-interp").style.display = p.interpretacion ? "" : "none";
    // Acciones derivadas
    if (p.acciones && p.acciones.length) {
      $("modal-acciones").innerHTML = `<h4>Posibles acciones derivadas</h4><ul>` +
        p.acciones.map((a) => `<li>${esc(a)}</li>`).join("") + `</ul>`;
      $("modal-acciones").style.display = "";
    } else { $("modal-acciones").style.display = "none"; }
    const res = dibujarModal(p);   // {cols, filas, csv} o null
    pintarTablaModal(res);
    ov.hidden = false;
    $("modal-x").focus();
    if (!res) {
      $("modal-meta").innerHTML = '<span class="aviso">No hay una gráfica disponible para esta pregunta.</span>';
    }
  }

  // Pinta la tabla dentro del modal y arma el botón de descarga (Blob, igual que el explorador)
  function pintarTablaModal(res) {
    const wrap = $("modal-tabla-wrap"), tabla = $("modal-tabla"), foot = $("modal-foot");
    if (!res || !res.filas || !res.filas.length) {
      if (wrap) wrap.style.display = "none";
      if (foot) foot.innerHTML = "";
      return;
    }
    wrap.style.display = "";
    wrap.open = false;
    tabla.innerHTML = `<table><thead><tr>${res.cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${res.filas.map((f) => `<tr>${f.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    foot.innerHTML = `<button type="button" id="modal-csv">⬇ Descargar CSV</button>`;
    $("modal-csv").onclick = () => descargarCSV(res.cols, res.filas, res.csv || "datos.csv");
  }
  function descargarCSV(cols, filas, nombre) {
    const celda = (v) => { const s = (v === null || v === undefined) ? "" : String(v);
      return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    const texto = "\ufeff" + [cols, ...filas].map((f) => f.map(celda).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([texto], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = nombre; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
  }

  // Dibuja en #modal-canvas y devuelve {cols, filas, csv} para la tabla/descarga, o null
  function dibujarModal(p) {
    const KB = KBG || {}; const ind = KB.indicadores || {};
    if (p.vista === "territorio") return modalTerritorio(KB, p.clave);
    if (p.vista === "ciudad_tiempo") return modalCiudadTiempo(ind, p.clave);
    if (p.vista === "aire") return modalAire(ind.pm25_siata);
    if (p.vista === "indice") return modalIndice();
    return null;
  }

  function modalTerritorio(KB, clave) {
    const pan = prepararPanorama(KB); if (!pan) return null;
    const meta = pan.cat.find((c) => c.clave === clave) || {};
    const valores = (pan.datos[clave] || {}).valores || {};
    const anio = ultimoAnioDesde(valores);
    const filas = Object.entries(valores)
      .map(([cod, serie]) => ({ nombre: pan.terr[cod] || cod, v: Number(serie[anio]) }))
      .filter((x) => !isNaN(x.v)).sort((a, b) => b.v - a.v);
    if (!filas.length) return null;
    $("modal-meta").innerHTML = `<b>${esc(meta.nombre || clave)}</b>${meta.unidad ? " · " + esc(meta.unidad) : ""} · ${anio || "s/d"} · por territorio`;
    $("modal-fuente").innerHTML = `<b>Fuente:</b> ${esc(meta.fuente || "Base de conocimiento del pipeline")} · Comparación entre territorios; asociación, no causalidad.`;
    nuevoGrafico("modal-canvas", { type: "bar",
      data: { labels: filas.map((f) => corto(f.nombre)),
        datasets: [{ data: filas.map((f) => f.v), backgroundColor: filas.map((_f, i) => (i < 3 ? NAR : AZUL)) }] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } } });
    return { cols: ["Territorio", `${meta.nombre || clave} (${anio || "s/d"})`],
      filas: filas.map((f) => [f.nombre, f.v]), csv: `${clave}_${anio || "medellin"}.csv` };
  }

  function modalCiudadTiempo(ind, clave) {
    const todas = seriesSalud(ind);
    const pref = { mortalidad_dane: "dane", sivigila: "sivi", rips: "rips" }[clave] || "";
    const s = todas.find((x) => x.id.startsWith(pref)) || todas[0];
    if (!s) return null;
    const pts = puntosSerie(s);
    if (!pts.length) return null;
    $("modal-meta").innerHTML = `<b>${esc(s.etiqueta)}</b> · nivel municipio (Medellín)`;
    $("modal-fuente").innerHTML = `<b>Fuente:</b> ${esc(s.fuente)} · <b>Unidad:</b> ${esc(s.unidad)} · ${esc(s.nota || "")}`;
    nuevoGrafico("modal-canvas", { type: "line",
      data: { labels: pts.map((pt) => pt.x),
        datasets: [{ data: pts.map((pt) => pt.y), borderColor: AZUL, backgroundColor: AZUL,
          pointRadius: s.tipo === "semanal" ? 0 : 2, borderWidth: 1.5, tension: 0.2 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { ticks: { maxTicksLimit: 12, autoSkip: true } }, y: { beginAtZero: true } } } });
    return { cols: ["Periodo", s.unidad || "Valor"],
      filas: pts.map((pt) => [pt.x, pt.y]), csv: `${s.id}_medellin.csv` };
  }

  function modalAire(pm) {
    if (!pm || !pm.ranking || !pm.ranking.length) return null;
    const cmp = pm.comparacion;
    const est = cmp ? [...cmp.estaciones].sort((a, b) => b.actual - a.actual) : null;
    const OMS = { eje: "y", valor: 5, color: ROJO, texto: "OMS 5 µg/m³" };
    const datasets = est
      ? [{ label: String(cmp.anio_anterior), data: est.map((e) => e.anterior), backgroundColor: "#a9c7e6" },
         { label: String(cmp.anio_actual), data: est.map((e) => e.actual), backgroundColor: AZUL }]
      : [{ label: String(pm.anio), data: pm.ranking.map((x) => x.media_pm25), backgroundColor: AZUL }];
    $("modal-meta").innerHTML = `<b>PM2.5 media anual por estación (SIATA)</b>${cmp ? ` · ${cmp.anio_anterior} vs ${cmp.anio_actual}` : " · " + pm.anio}`;
    $("modal-fuente").innerHTML = `<b>Fuente:</b> SIATA · ⚠️ ${esc(pm.advertencia || "")} Por estación, no por comuna.`;
    nuevoGrafico("modal-canvas", { type: "bar",
      data: { labels: (est || pm.ranking).map((x) => x.estacion), datasets },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: !!est }, lineasRef: { lineas: [OMS] } },
        scales: { y: { beginAtZero: true, title: { display: true, text: "PM2.5 media anual (µg/m³)" } } } },
      plugins: [lineasRef] });
    const cols = est ? ["Estación", String(cmp.anio_anterior), String(cmp.anio_actual)] : ["Estación", `PM2.5 ${pm.anio}`];
    const filas = est ? est.map((e) => [e.estacion, e.anterior, e.actual]) : pm.ranking.map((x) => [x.estacion, x.media_pm25]);
    return { cols, filas, csv: "pm25_estaciones.csv" };
  }

  function modalIndice() {
    if (!T.length || !T.every((t) => t.ts != null)) return null;
    const datos = T.map((t) => ({ nombre: t.nombre, v: indiceCon(t, 50) })).sort((a, b) => b.v - a.v);
    $("modal-meta").innerHTML = `<b>Índice de priorización en salud</b> · mortalidad 50 % + salud mental 50 % · 0–100`;
    $("modal-fuente").innerHTML = `<b>Fuente:</b> MEData (mortalidad e intento de suicidio), normalizado min-max. Índice base del proyecto.`;
    nuevoGrafico("modal-canvas", { type: "bar",
      data: { labels: datos.map((d) => corto(d.nombre)),
        datasets: [{ data: datos.map((d) => +d.v.toFixed(1)), backgroundColor: datos.map((_d, i) => (i < 3 ? NAR : AZUL)) }] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } }, scales: { x: { min: 0, max: 100 } } } });
    return { cols: ["Territorio", "Índice (0–100)"],
      filas: datos.map((d) => [d.nombre, +d.v.toFixed(1)]), csv: "indice_priorizacion.csv" };
  }

  (function () {
    const els = document.querySelectorAll(".rev");
    if (!("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("vis")); return; }
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("vis"); io.unobserve(e.target); } }), { threshold: 0.08 });
    els.forEach((e) => io.observe(e));
  })();

  /* ---------- 7. Flujo interactivo del método ---------- */
  let KBG = null, pasoActual = 0, temporizador = null;
  let DESCG = {};  // descripciones curadas por clave (docs/descripciones.json); {} si no carga
  let CTXG = {};   // hipótesis de contexto curadas por clave (comportamiento histórico)
  let DISPG = {};  // hipótesis de dispersión territorial curadas por clave
  let TAPG = {};   // coletilla curada de apertura del análisis territorial por clave
  let GVALG = {};  // glosa curada del valor (magnitud | unidad glosada) por clave
  let GBRG = {};   // coletilla curada de la brecha por clave
  let FLEG = {};   // nombres legibles de fuentes (identificador KB → nombre institucional)
  let INFRAG = {}; // matiz de infraestructura por clave (nota de controles ausentes)
  let SREDG = {};  // coletilla curada de la situación de reducción por clave
  let ACTG = {};   // adjetivo de 'actividad' por clave (viñeta de concentración)
  let IMPG = {};   // implicaciones de gestión curadas por clave (array de líneas)
  let CONCG = {};  // conclusión ejecutiva curada por clave
  const PASOS = [
    { ico: "⬇️", n: "Descargar", script: "scripts/01_descargar.py",
      desc: "Baja los datos únicamente desde las URLs oficiales del manifiesto sources.yml. No modifica ni interpreta nada: solo descarga y registra la procedencia.",
      entra: ["ECV 2022–2025 (Alcaldía de Medellín)", "SIATA · PM2.5 validado 2024–2025", "MEData · VC_Datos_Enfermedades (mortalidad, intento de suicidio, natalidad)"],
      sale: ["data/raw/ (no se publica)", "manifiesto de descarga con la procedencia"], garantia: "Datos reales, nunca sintéticos." },
    { ico: "✅", n: "Validar", script: "scripts/03_validar.py",
      desc: "Comprueba que la llave territorial sea consistente entre años y cubra los 21 territorios (16 comunas + 5 corregimientos). Si una base no cumple, el pipeline se detiene y el fallo queda visible.",
      entra: ["Bases ECV 2022–2025"], sale: ["«VALIDACIÓN OK: llave territorial consistente»"], garantia: "El código 99 «sin información» se excluye.",
      vivo: (k) => `${(k.meta || {}).territorios_oficiales || 21} territorios oficiales en el KB.` },
    { ico: "🧹", n: "Limpiar", script: "scripts/02_limpiar.py",
      desc: "Homologa la variable territorial, que cambia de nombre cada año (p_006 / P_007 / A.7), a una columna común y añade los nombres oficiales. Lee por bloques para no agotar la memoria.",
      entra: ["Bases ECV originales"], sale: ["Parquet liviano en data/processed/ (no se publica)"], garantia: "No se cruzan microdatos individuales entre fuentes." },
    { ico: "🔗", n: "Integrar", script: "scripts/04_integrar.py",
      desc: "Combina las bases en una tabla agregada por territorio y año. Es la única tabla derivada de la ECV que se publica.",
      entra: ["Parquet homologado"], sale: ["outputs/tablas/resumen_territorial.csv"], garantia: "Solo agregados, sin datos personales.",
      vivo: (k) => { const c = (k.territorios || {}).cobertura_ecv; return c ? `Cobertura ECV en ${Object.keys(c).length} territorios, años ${((k.territorios || {}).anios_disponibles || []).join(", ")}.` : null; } },
    { ico: "📊", n: "Analizar", script: "scripts/05_analizar.py",
      desc: "Cruza por comuna la mortalidad y el intento de suicidio (MEData), calcula la brecha y la variación 2012–2022, y construye el índice de priorización (min-max 0–100).",
      entra: ["MEData · mortalidad e intento de suicidio", "Resumen territorial ECV"], sale: ["hallazgo.json", "analisis_mortalidad_comuna.csv", "indice_priorizacion_comuna.csv"], garantia: "Cada cifra sale del cálculo, no se escribe a mano.",
      vivo: (k) => { const h = (k.indicadores || {}).hallazgo_mortalidad; return h && h.brecha_veces ? `Brecha calculada: ${fmt(h.brecha_veces, 2)}× entre ${h.comuna_mayor_tasa.nombre} y ${h.comuna_menor_tasa.nombre}.` : null; } },
    { ico: "🖼️", n: "Visualizar", script: "scripts/06_visualizar.py",
      desc: "Genera los gráficos PNG sin necesidad de pantalla y el diagrama del pipeline, para la ficha de hallazgos.",
      entra: ["Tablas de outputs/tablas/"], sale: ["outputs/graficos/*.png"], garantia: "Gráficos regenerados en cada ejecución." },
    { ico: "🌫️", n: "Aire", script: "scripts/08_siata.py",
      desc: "Extrae el PM2.5 de los ZIP mensuales de SIATA y lo agrega por estación y año, exigiendo ≥ 75 % de datos válidos. No atribuye PM2.5 a comunas.",
      entra: ["ZIP mensuales de SIATA"], sale: ["outputs/tablas/siata_pm25_estacion.csv"], garantia: "Se reporta por estación, con su advertencia metodológica.",
      vivo: (k) => { const pm = (k.indicadores || {}).pm25_siata; return pm && pm.ranking ? `${pm.ranking.length} estaciones con dato en ${pm.anio}.` : null; } },
    { ico: "🧠", n: "Knowledge base", script: "scripts/07_construir_kb.py",
      desc: "Consolida todo en un único JSON que alimenta este portal y el asistente. El asistente solo lee ese archivo: nunca vuelve a tocar los microdatos.",
      entra: ["Tablas y hallazgo del análisis"], sale: ["outputs/kb/knowledge_base.json", "docs/knowledge_base.json (portal)"], garantia: "El asistente no puede inventar cifras: solo recupera las del KB.",
      vivo: (k) => ((k.meta || {}).generado_utc ? `Última generación: ${k.meta.generado_utc} UTC.` : null) },
    { ico: "🚀", n: "Probar y publicar", script: ".github/workflows/pipeline.yml",
      desc: "Ejecuta las pruebas automáticas del asistente (si fallan, el workflow se detiene), guarda los resultados como artefacto y hace commit automático. GitHub Pages republica este portal.",
      entra: ["knowledge_base.json y tablas"], sale: ["Artefacto «resultados-ecv»", "Commit automático de outputs/ y docs/", "Portal actualizado"], garantia: "Del dato oficial a este portal sin pasos manuales." },
  ];
  const lista = (a) => `<ul>${a.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  function pintarPaso() {
    document.querySelectorAll(".paso").forEach((b, i) => {
      b.classList.toggle("activo", i === pasoActual);
      b.classList.toggle("hecho", i < pasoActual);
      if (i === pasoActual) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    });
    $("prog").style.width = ((pasoActual + 1) / PASOS.length * 100) + "%";
    const p = PASOS[pasoActual];
    const vivo = p.vivo && KBG ? p.vivo(KBG) : null;
    $("detalle").innerHTML = `
      <div><h3>${pasoActual + 1}. ${esc(p.n)}</h3><p style="margin:0 0 8px">${esc(p.desc)}</p>
        <code>${esc(p.script)}</code>
        ${vivo ? `<div class="vivo" style="margin-top:10px"><b>Resultado en vivo:</b> ${esc(vivo)}</div>` : ""}
        <div class="garantia">✔ ${esc(p.garantia)}</div></div>
      <div><h4>Entra</h4>${lista(p.entra)}<h4>Sale</h4>${lista(p.sale)}</div>`;
  }
  function irAPaso(i) { pasoActual = Math.max(0, Math.min(PASOS.length - 1, i)); pintarPaso(); }
  function detener() { if (temporizador) { clearInterval(temporizador); temporizador = null; } $("f-play").textContent = "▶ Reproducir flujo"; }
  function reproducir() {
    if (temporizador) return detener();
    $("f-play").textContent = "⏸ Pausar";
    if (pasoActual >= PASOS.length - 1) irAPaso(0);
    temporizador = setInterval(() => {
      if (pasoActual >= PASOS.length - 1) return detener();
      irAPaso(pasoActual + 1);
      if (pasoActual >= PASOS.length - 1) detener();
    }, 1900);
  }
  function iniciarFlujo() {
    $("pasos").innerHTML = PASOS.map((p, i) =>
      `<li><button type="button" class="paso" data-i="${i}"><span class="ico" aria-hidden="true">${p.ico}</span><span class="num">${i + 1}</span><span>${esc(p.n)}</span></button></li>`).join("");
    document.querySelectorAll(".paso").forEach((b) => { b.onclick = () => { detener(); irAPaso(+b.dataset.i); }; });
    $("f-ant").onclick = () => { detener(); irAPaso(pasoActual - 1); };
    $("f-sig").onclick = () => { detener(); irAPaso(pasoActual + 1); };
    $("f-play").onclick = reproducir;
    irAPaso(0);
  }
  iniciarFlujo();

  /* ---------- Arranque ---------- */
  // Inyecta el mapa real de los 21 territorios (SVG propio generado en Actions por
  // scripts/13_mapa_hero.py). connect-src 'self' permite el fetch; si falla, queda el fallback.
  function cargarMapaHero() {
    const cont = $("hero-mapa"); if (!cont) return;
    const src = cont.getAttribute("data-src") || "mapa_comunas.svg";
    fetch(src, { cache: "force-cache" })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error("HTTP " + r.status))))
      .then((svg) => {
        if (svg.indexOf("<svg") >= 0 && svg.indexOf("</svg>") >= 0) cont.innerHTML = svg;
      })
      .catch((err) => { console.warn("mapa_comunas.svg no disponible, se usa el fallback:", err.message); });
  }

  // ----- Sección Mapa: coropleta por indicador (repinta el SVG real) + red de correlaciones -----
  const RAMPA = [[44, 123, 182], [255, 255, 191], [215, 25, 28]];  // azul→amarillo→rojo
  function rampaColor(t) {
    const seg = t <= 0.5 ? 0 : 1, lt = t <= 0.5 ? t / 0.5 : (t - 0.5) / 0.5;
    const a = RAMPA[seg], b = RAMPA[seg + 1];
    const m = (i) => Math.round(a[i] + (b[i] - a[i]) * lt);
    return `rgb(${m(0)},${m(1)},${m(2)})`;
  }
  const normNom = (s) => String(s || "").replace(/^Corregimiento de\s+/i, "").trim().toLowerCase();

  function iniciarMapa() {
    const cont = $("co-mapa"); if (!cont) return;
    const KB = KBG || {}; const S = KB.series || {}; const dat = S.datos || {};
    const terr = S.territorios || {}; const catl = S.catalogo || [];
    const metaDe = (cl) => catl.find((c) => c.clave === cl) || {};
    const idxNombre = {}; Object.keys(terr).forEach((k) => { idxNombre[normNom(terr[k])] = k; });

    fetch("mapa_comunas.svg", { cache: "force-cache" })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error("HTTP " + r.status))))
      .then((svgTxt) => {
        const selI = $("co-ind"), selA = $("co-anio");
        const conVal = catl.filter((c) => (dat[c.clave] || {}).valores);
        if (!conVal.length || !selI || !selA) return;
        selI.innerHTML = conVal.map((c) => `<option value="${esc(c.clave)}">${esc(c.nombre)}</option>`).join("");
        if (conVal.some((c) => c.clave === "mortalidad")) selI.value = "mortalidad";

        const aniosDe = (cl) => {
          const v = (dat[cl] || {}).valores || {}; const s = new Set();
          Object.values(v).forEach((se) => Object.keys(se).forEach((a) => s.add(a)));
          return [...s].sort();
        };
        const recargaAnios = () => {
          const aa = aniosDe(selI.value);
          selA.innerHTML = aa.map((a) => `<option value="${a}">${a}</option>`).join("");
          if (aa.length) selA.value = aa[aa.length - 1];
        };
        const pintar = () => {
          const cl = selI.value, anio = selA.value;
          const vals = (dat[cl] || {}).valores || {};
          const puntos = {}; let mn = Infinity, mx = -Infinity;
          Object.keys(vals).forEach((cod) => {
            const v = Number((vals[cod] || {})[anio]);
            if (!isNaN(v)) { puntos[String(parseInt(cod, 10))] = v; mn = Math.min(mn, v); mx = Math.max(mx, v); }
          });
          cont.innerHTML = svgTxt;
          const svgEl = cont.querySelector("svg"); if (!svgEl) return;
          svgEl.querySelectorAll("path").forEach((p) => {
            const titulo = (p.querySelector("title") || {}).textContent || "";
            p.setAttribute("class", "ch-terr");
            const codKB = idxNombre[normNom(titulo)];
            const v = codKB != null ? puntos[String(parseInt(codKB, 10))] : undefined;
            if (v == null || mx === mn) p.setAttribute("fill", "rgba(31,78,121,.10)");
            else p.setAttribute("fill", rampaColor((v - mn) / (mx - mn)));
            const t = p.querySelector("title"); if (t) t.textContent = titulo + (v != null ? `: ${fmt(v, 1)}` : " (sin dato)");
          });
          const u = metaDe(cl).unidad || "";
          if ($("co-min")) $("co-min").textContent = isFinite(mn) ? `${fmt(mn, 1)} ${u}` : "";
          if ($("co-max")) $("co-max").textContent = isFinite(mx) ? `${fmt(mx, 1)} ${u}` : "";
          if ($("co-ley")) $("co-ley").textContent = `${metaDe(cl).nombre || cl} · ${anio} · 21 territorios`;
        };
        selI.onchange = () => { recargaAnios(); pintar(); };
        selA.onchange = pintar;
        recargaAnios(); pintar();
      })
      .catch((err) => { cont.textContent = "No se pudo cargar el mapa."; console.warn("mapa:", err.message); });

    // Red de correlaciones significativas (radial desde los resultados de salud)
    const destino = $("red-svg"); if (!destino) return;
    const corr = (S.correlaciones || []).filter((c) => c && c.significativa);
    const seen = new Set(), aristas = [];
    corr.forEach((c) => { const k = [c.resultado, c.factor].sort().join("|"); if (!seen.has(k)) { seen.add(k); aristas.push(c); } });
    if (!aristas.length) { destino.textContent = "Sin correlaciones significativas en el KB."; return; }
    const nom = (k) => metaDe(k).nombre || k;
    const resultados = [...new Set(aristas.map((a) => a.resultado))];
    const factores = [...new Set(aristas.map((a) => a.factor))];
    const W = 620, H = 440, cx = W / 2, cy = H / 2, R = 165;
    const posR = {}; resultados.forEach((r, i) => { posR[r] = [cx + (resultados.length === 1 ? 0 : (i === 0 ? -80 : 80)), cy]; });
    const posF = {}; factores.forEach((f, i) => { const ang = (-90 + i * (360 / factores.length)) * Math.PI / 180; posF[f] = [cx + R * Math.cos(ang), cy + R * Math.sin(ang)]; });
    const maxr = Math.max(...aristas.map((a) => Math.abs(a.pearson || 0))) || 1;
    const corto = (s) => (s.length > 24 ? s.slice(0, 22) + "…" : s);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Red de correlaciones significativas del KB">`;
    aristas.forEach((a) => {
      const pr = posR[a.resultado], pf = posF[a.factor]; if (!pr || !pf) return;
      const w = 1 + 5 * Math.abs(a.pearson || 0) / maxr;
      const cls = (a.pearson || 0) >= 0 ? "red-arista red-pos" : "red-arista red-neg";
      svg += `<line class="${cls}" x1="${pr[0].toFixed(0)}" y1="${pr[1].toFixed(0)}" x2="${pf[0].toFixed(0)}" y2="${pf[1].toFixed(0)}" stroke-width="${w.toFixed(1)}"><title>${esc(nom(a.resultado))} ~ ${esc(nom(a.factor))} (r=${fmt(a.pearson, 2)})</title></line>`;
    });
    const dibNodo = (x, y, r, cls, lbl, anchor) => {
      const tx = anchor === "start" ? x + 9 : anchor === "end" ? x - 9 : x;
      return `<circle class="${cls}" cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${r}"><title>${esc(lbl)}</title></circle>` +
        `<text class="red-lbl" x="${tx.toFixed(0)}" y="${(y - r - 4).toFixed(0)}" text-anchor="${anchor}">${esc(corto(lbl))}</text>`;
    };
    Object.entries(posF).forEach(([f, p]) => { svg += dibNodo(p[0], p[1], 6, "red-nodo", nom(f), p[0] > cx ? "start" : "end"); });
    Object.entries(posR).forEach(([r, p]) => { svg += dibNodo(p[0], p[1], 11, "red-nodo salud", nom(r), "middle"); });
    svg += "</svg>";
    destino.innerHTML = svg;

    // Análisis de la red (debajo del grafo), 100 % derivado de las correlaciones significativas del KB.
    const contAna = $("red-analisis");
    if (contAna) {
      const nDir = aristas.filter((a) => (a.pearson || 0) >= 0).length;
      const nInv = aristas.length - nDir;
      const rs = aristas.map((a) => Math.abs(a.pearson || 0));
      const rMin = Math.min(...rs), rMax = Math.max(...rs);
      const fuerte = aristas.slice().sort((a, b) => Math.abs(b.pearson || 0) - Math.abs(a.pearson || 0))[0];
      // factor que más veces aparece
      const cuenta = {};
      aristas.forEach((a) => { cuenta[a.factor] = (cuenta[a.factor] || 0) + 1; });
      const topFactor = Object.entries(cuenta).sort((x, y) => y[1] - x[1])[0];
      const porResultado = {};
      resultados.forEach((r) => { porResultado[r] = aristas.filter((a) => a.resultado === r).length; });
      const detalleRes = Object.entries(porResultado)
        .map(([r, n]) => `<b>${esc(nom(r))}</b> (${n})`).join(" y ");

      let html = `<h4>Lectura de la red</h4>`;
      html += `<p>Se detectaron <b>${aristas.length}</b> asociaciones estadísticamente significativas entre los 21 territorios `;
      html += `(Pearson y Spearman al 95%): ${nDir} en la misma dirección y ${nInv} inversa(s). `;
      html += `La intensidad va de r=${fmt(rMin, 2)} a r=${fmt(rMax, 2)}. `;
      html += `Las relaciones parten de los resultados de salud: ${detalleRes}.</p>`;
      html += `<ul>`;
      if (fuerte) {
        const signo = (fuerte.pearson || 0) >= 0 ? "directa" : "inversa";
        html += `<li>Asociación más fuerte: <b>${esc(nom(fuerte.resultado))}</b> y <b>${esc(nom(fuerte.factor))}</b> (r=${fmt(fuerte.pearson, 2)}, ${signo}).</li>`;
      }
      if (topFactor && topFactor[1] > 1) {
        html += `<li>Factor con más vínculos: <b>${esc(nom(topFactor[0]))}</b>, asociado en ${topFactor[1]} relaciones.</li>`;
      }
      if (nInv) {
        const inv = aristas.filter((a) => (a.pearson || 0) < 0)
          .map((a) => `${esc(nom(a.resultado))}–${esc(nom(a.factor))}`).join("; ");
        html += `<li>Relación(es) inversa(s): ${inv}. Un signo negativo puede reflejar efectos de composición (p. ej. estructura de edad del territorio), no protección causal.</li>`;
      }
      html += `</ul>`;
      html += `<p class="nota">Lectura ecológica entre territorios: describe patrones conjuntos, no causalidad. No se controla por estructura de edad ni otros confusores.</p>`;
      contAna.innerHTML = html;
    }
  }

  function pintarPortal(KB) {
    const ind = KB.indicadores || {};
    KBG = KB; pintarPaso();
    construirTerritorios(ind);   // llena T (nm/ns/ts) → necesario para el índice en el modal
    pintarHero(KB);
    cargarMapaHero();            // mapa real del hero (contorno por comuna)
    if (T.length) sel = T[0].nombre;
    iniciarPreguntas();          // observatorio: categorías + preguntas + modal (reusa datos del KB)
    iniciarMapa();               // sección Mapa: coropleta por indicador + red de correlaciones
  }
  window.Asistente.cargarKB()
    .then((KB) => {
      return fetch("descripciones.json", { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null)
        .then((desc) => { DESCG = (desc && desc.descripciones) || {}; CTXG = (desc && desc.contexto) || {}; DISPG = (desc && desc.dispersion) || {}; TAPG = (desc && desc.territorio_apertura) || {}; GVALG = (desc && desc.glosa_valor) || {}; GBRG = (desc && desc.glosa_brecha) || {}; FLEG = (desc && desc.fuentes_legibles) || {}; INFRAG = (desc && desc.infraestructura) || {}; SREDG = (desc && desc.situacion_reduccion) || {}; ACTG = (desc && desc.actividad) || {}; IMPG = (desc && desc.implicaciones) || {}; CONCG = (desc && desc.conclusion) || {}; return KB; });
    })
    .then((KB) => {
      pintarPortal(KB);
      const g = (KB.meta || {}).generado_utc;
      $("estado").textContent = "Datos cargados desde knowledge_base.json (generado por el pipeline" + (g ? ` · última actualización ${g} UTC` : "") + ").";
    })
    .catch((err) => { $("estado").innerHTML = '<span class="aviso">No se pudo cargar knowledge_base.json: ' + esc(err.message) + "</span>"; console.error(err); });
