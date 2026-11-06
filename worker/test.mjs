// Pruebas del Worker sin red ni clave real (fetch de Gemini simulado).
// Uso: node worker/test.mjs
import assert from "node:assert/strict";
import worker, { sanear, catalogo, _limpiarCache } from "./src/index.js";

const ORIGEN = "https://watabares.github.io";
let respuestaGemini = null, llamadas = 0, kbFalla = false, cuerpoGemini = null;
const KB_FALSO = { series: { catalogo: [{ clave: "mortalidad", nombre: "mortalidad general" },
                                        { clave: "dengue", nombre: "dengue" },
                                        { clave: "mal clave!", nombre: "inyección" }] } };
globalThis.fetch = async (url, opts) => {
  if (String(url).includes("knowledge_base.json")) {
    if (kbFalla) throw new Error("sin red");
    return { ok: true, json: async () => KB_FALSO };
  }
  llamadas++;
  cuerpoGemini = JSON.parse(opts.body);
  return { ok: true, json: async () => ({ candidates: [{ content: { parts: [{ text: JSON.stringify(respuestaGemini) }] } }] }) };
};
const env = { GEMINI_API_KEY: "x" };
const req = (body, origen = ORIGEN, metodo = "POST") =>
  new Request("https://w.example/interpretar", { method: metodo,
    headers: { "Content-Type": "application/json", ...(origen ? { Origin: origen } : {}) },
    body: metodo === "POST" ? JSON.stringify(body) : undefined });

let ok = 0;
const caso = async (nombre, fn) => { await fn(); ok++; console.log("[PASS]", nombre); };

await caso("respuesta válida y saneada", async () => {
  respuestaGemini = { intencion: "territorio", territorios: ["La Candelaria"], indicador: "dengue",
                      anios: [2015, 2020], causa: true };
  const r = await worker.fetch(req({ pregunta: "dengue en el centro entre 2015 y 2020" }), env);
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("Access-Control-Allow-Origin"), ORIGEN);
  const d = await r.json();
  assert.deepEqual([d.intencion, d.territorios, d.indicador, d.anios, d.causa],
                   ["territorio", ["La Candelaria"], "dengue", [2015, 2020], true]);
  // El esquema enviado a Gemini restringe el indicador al catálogo del KB (+ pm25).
  const enumInd = cuerpoGemini.generationConfig.responseSchema.properties.indicador.enum;
  assert.deepEqual(enumInd, ["ninguno", "mortalidad", "dengue", "pm25"]);
  assert.ok(enumInd.every((v) => v.length > 0), "Gemini rechaza valores vacíos en enum");
});

await caso("origen ajeno -> 403 sin llamar a Gemini", async () => {
  const n = llamadas;
  const r = await worker.fetch(req({ pregunta: "hola" }, "https://malo.example"), env);
  assert.equal(r.status, 403);
  assert.equal(llamadas, n);
});

await caso("sin Origin (curl) -> 403", async () => {
  assert.equal((await worker.fetch(req({ pregunta: "hola" }, null), env)).status, 403);
});

await caso("pregunta demasiado larga -> 400", async () => {
  assert.equal((await worker.fetch(req({ pregunta: "a".repeat(301) }), env)).status, 400);
});

await caso("preflight OPTIONS -> 204 con CORS", async () => {
  const r = await worker.fetch(req(null, ORIGEN, "OPTIONS"), env);
  assert.equal(r.status, 204);
  assert.match(r.headers.get("Access-Control-Allow-Methods"), /POST/);
});

await caso("sin clave -> 503", async () => {
  assert.equal((await worker.fetch(req({ pregunta: "hola" }), {})).status, 503);
});

await caso("límite por IP agotado -> 429", async () => {
  const e = { ...env, LIMITE_IP: { limit: async () => ({ success: false }) } };
  assert.equal((await worker.fetch(req({ pregunta: "hola" }), e)).status, 429);
});

await caso("sanear descarta valores fuera de lista (prompt injection)", async () => {
  const s = sanear({ intencion: "borrar_todo", territorios: ["<script>", "Manrique", "Manrique", "Robledo", "Popular"],
                     indicador: "rm -rf", anios: [2015, "2016", 9999, 2015, 2018, 2019], causa: "si" },
                   [{ clave: "mortalidad" }]);
  assert.deepEqual(s, { intencion: "fuera_de_alcance", territorios: ["Manrique", "Robledo"],
                        indicador: "", anios: [2015, 2018], causa: false });
});

await caso("indicador 'ninguno' se convierte en vacío", async () => {
  assert.equal(sanear({ intencion: "tendencia", indicador: "ninguno" }, [{ clave: "mortalidad" }]).indicador, "");
});

await caso("KB caído: el catálogo queda solo con pm25 y no se cachea", async () => {
  _limpiarCache(); kbFalla = true;
  const c1 = await catalogo({});
  assert.deepEqual(c1.map((c) => c.clave), ["pm25"]);
  kbFalla = false;
  const c2 = await catalogo({});
  assert.deepEqual(c2.map((c) => c.clave), ["mortalidad", "dengue", "pm25"]);
});

console.log(`\n${ok}/10 pruebas OK`);
