// paridad_js.cjs — Ejecuta el motor web (docs/asistente.js) en Node para
// compararlo con motor.py. Lo usa test_motor.py (no se publica en el portal).
// Uso: node asistente/paridad_js.cjs <knowledge_base.json>  < preguntas.json
"use strict";
const fs = require("fs");
const path = require("path");
global.window = {};
eval(fs.readFileSync(path.join(__dirname, "..", "docs", "asistente.js"), "utf8"));
window.Asistente._setKB(JSON.parse(fs.readFileSync(process.argv[2], "utf8")));
const preguntas = JSON.parse(fs.readFileSync(0, "utf8"));
const out = preguntas.map((p) => {
  const r = Array.isArray(p) ? window.Asistente.responder(p[0], p[1]) : window.Asistente.responder(p);
  return { respuesta_directa: r.respuesta_directa, encontrado: r.encontrado,
           n_evidencia: (r.evidencia || []).length };
});
process.stdout.write(JSON.stringify(out));
