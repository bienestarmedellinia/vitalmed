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
      `<h2>Hallazgo principal</h2><p><b>${esc(top.nombre)}</b> tiene una tasa de mortalidad <b>${fmt(h.brecha_veces, 2)}×</b> la de ${esc(bajo.nombre)}
       (${fmt(top.tasa)} vs ${fmt(bajo.tasa)} por 100.000 hab., ${h.anio_referencia}).</p>
       <small>Fuente: MEData · Secretaría de Salud. Asociación, no causalidad.</small>`;
    const t3 = (((ind.indice_priorizacion || {}).ranking) || []).slice(0, 3).map((x) => x.nombre);
    $("hero-propuesta").innerHTML = t3.length
      ? `<h2>Propuesta de mejora</h2><p>Concentrar intervenciones integrales (salud física + salud mental) en <b>${esc(t3.join(", "))}</b>
         y monitorear ambos indicadores.</p><small>Según el índice de priorización; prueba otros pesos en el simulador.</small>`
      : `<h2>Propuesta de mejora</h2><p>Priorizar intervenciones en los territorios de mayor mortalidad.</p>`;
    const k = [
      [top.tasa, 1, "", "", "Mayor tasa de mortalidad", `${top.nombre} · por 100.000 hab. · ${h.anio_referencia}`],
      [h.brecha_veces, 2, "", "×", "Brecha entre territorios", `vs ${bajo.nombre}`],
      [h.variacion_pct_2012_2022_comuna_top, 1, h.variacion_pct_2012_2022_comuna_top >= 0 ? "+" : "", "%", "Variación 2012–2022", top.nombre],
    ];
    if (ciudad) k.push([ciudad, 0, "", "", "Tasa de toda la ciudad", "defunciones por 100.000 hab. · 2022"]);
    if (pm.ranking && pm.ranking.length)
      k.push([pm.ranking[0].media_pm25, 1, "", "", "PM2.5 máx. (µg/m³)", `Estación ${pm.ranking[0].estacion} · ${pm.anio} · OMS: 5`]);
    $("kpis").innerHTML = k.map((x, i) =>
      `<div class="kpi"><div class="n" id="kn${i}">0</div><div class="t">${esc(x[4])}</div><div class="s">${esc(x[5])}</div></div>`).join("");
    k.forEach((x, i) => contar($("kn" + i), x[0], x[1], x[2], x[3]));
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

  /* ---------- 4. Tendencia ---------- */
  function pintarTendencia(h) {
    const s = h.serie_temporal_comuna_top, top = h.comuna_mayor_tasa; if (!s || !s.anios) return;
    $("tend-sub").textContent = `${top ? top.nombre : "La comuna con mayor tasa"}: ${fmt(s.tasas[0])} en ${s.anios[0]} → ${fmt(s.tasas[s.tasas.length - 1])} en ${s.anios[s.anios.length - 1]} defunciones por 100.000 hab.`;
    const dibujar = (base) => {
      const vals = base ? s.tasas.map((v) => +(v / s.tasas[0] * 100).toFixed(1)) : s.tasas;
      const i21 = s.anios.indexOf(2021);
      nuevoGrafico("c-tend", { type: "line",
        data: { labels: s.anios.map(String), datasets: [{ data: vals, borderColor: NAR, backgroundColor: "rgba(217,115,26,.15)", fill: true, tension: .25,
          pointRadius: s.anios.map((_, i) => (i === i21 ? 8 : 4)), pointBackgroundColor: s.anios.map((_, i) => (i === i21 ? ROJO : NAR)) }] },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, lineasRef: { lineas: base ? [{ eje: "y", valor: 100, color: "#6b7280", texto: "2012 = 100" }] : [] } },
          scales: { y: { title: { display: true, text: base ? "Índice (2012 = 100)" : "Defunciones por 100.000 hab." } } } },
        plugins: [lineasRef] });
    };
    const alt = (base) => { $("t-abs").setAttribute("aria-pressed", String(!base)); $("t-base").setAttribute("aria-pressed", String(base)); dibujar(base); };
    $("t-abs").onclick = () => alt(false); $("t-base").onclick = () => alt(true);
    dibujar(false);
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
    "¿Cuál es el hallazgo principal?",
    "¿Qué comunas deberían recibir mayor atención en salud?",
    "¿Qué territorio tiene la menor tasa de mortalidad?",
    "Si hay presupuesto para 3 territorios, ¿cuáles priorizar?",
    "¿Cómo varió la mortalidad entre 2012 y 2022?",
    "¿Qué relación hay entre la contaminación del aire y la salud?",
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
    if (!r.encontrado) html += `<p class="aviso">Sin cifra directa para esta consulta.</p>`;
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
    const esLinea = g.tipo === "line", ds = { label: g.etiqueta_eje, data: g.valores };
    if (esLinea) Object.assign(ds, { borderColor: NAR, backgroundColor: NAR, tension: .25, fill: false, pointRadius: 4 });
    else ds.backgroundColor = g.resaltar.map((on) => (on ? NAR : AZUL));
    nuevoGrafico("chart", { type: g.tipo, data: { labels: g.labels, datasets: [ds] },
      options: { indexAxis: esLinea ? "x" : "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, title: { display: true, text: g.titulo } },
        scales: esLinea ? { y: { title: { display: true, text: g.etiqueta_eje } } } : { x: { title: { display: true, text: g.etiqueta_eje } } } } });
  }
  SUGERIDAS.forEach((s) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = s;
    b.onclick = () => { $("q").value = s; preguntar(true); };
    $("sugeridas").appendChild(b);
  });
  const RAPIDAS = [
    ["Hallazgo principal", "¿Cuál es el hallazgo principal?"],
    ["Qué territorios priorizar", "Si hay presupuesto para 3 territorios, ¿cuáles priorizar?"],
    ["Análisis de calidad del aire", "¿Qué relación hay entre la contaminación del aire y la salud?"],
    ["Evolución 2012–2022", "¿Cómo varió la mortalidad entre 2012 y 2022?"],
  ];
  RAPIDAS.forEach(([txt, preg]) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = txt;
    b.onclick = () => {
      $("q").value = preg; preguntar(true);
      $("asistente").scrollIntoView({ behavior: REDUCIR ? "auto" : "smooth" });
    };
    $("rapidas").appendChild(b);
  });
  $("btn-preguntar").onclick = () => preguntar(false);
  $("q").addEventListener("keydown", (e) => { if (e.key === "Enter") preguntar(false); });

  /* ---------- Revelado al hacer scroll ---------- */
  (function () {
    const els = document.querySelectorAll(".rev");
    if (!("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("vis")); return; }
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("vis"); io.unobserve(e.target); } }), { threshold: 0.08 });
    els.forEach((e) => io.observe(e));
  })();

  /* ---------- 7. Flujo interactivo del método ---------- */
  let KBG = null, pasoActual = 0, temporizador = null;
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
  function pintarPortal(KB) {
    const ind = KB.indicadores || {};
    KBG = KB; pintarPaso();
    construirTerritorios(ind);
    pintarHero(KB);
    if (T.length) {
      sel = T[0].nombre;
      $("m-tasa").onclick = () => { modoMort = "tasa"; $("m-tasa").setAttribute("aria-pressed", "true"); $("m-casos").setAttribute("aria-pressed", "false"); pintarMortalidad(); };
      $("m-casos").onclick = () => { modoMort = "casos"; $("m-casos").setAttribute("aria-pressed", "true"); $("m-tasa").setAttribute("aria-pressed", "false"); pintarMortalidad(); };
      pintarFicha(); pintarMortalidad();
      if (T.every((t) => t.ts != null)) {
        pintarDispersion(); pintarSimulador(); pintarRobustez();
        $("peso").addEventListener("input", pintarSimulador);
        resaltarDisp();
      }
    }
    pintarTendencia(ind.hallazgo_mortalidad || {});
    pintarAire(ind.pm25_siata);
  }
  window.Asistente.cargarKB()
    .then((KB) => {
      pintarPortal(KB);
      const g = (KB.meta || {}).generado_utc;
      $("estado").textContent = "Datos cargados desde knowledge_base.json (generado por el pipeline" + (g ? ` · última actualización ${g} UTC` : "") + ").";
    })
    .catch((err) => { $("estado").innerHTML = '<span class="aviso">No se pudo cargar knowledge_base.json: ' + esc(err.message) + "</span>"; console.error(err); });
