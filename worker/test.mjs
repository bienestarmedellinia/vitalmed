// Pruebas del Worker sin red ni clave real (fetch de Gemini simulado).
// Uso: node worker/test.mjs
import assert from "node:assert/strict";
import worker, { sanear } from "./src/index.js";

const ORIGEN = "https://watabares.github.io";
let respuestaGemini = null, llamadas = 0;
globalThis.fetch = async () => {
  llamadas++;
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
  respuestaGemini = { intencion: "territorio", territorios: ["La Candelaria"], causa: true };
  const r = await worker.fetch(req({ pregunta: "por qué mueren tanto en el centro" }), env);
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("Access-Control-Allow-Origin"), ORIGEN);
  const d = await r.json();
  assert.deepEqual([d.intencion, d.territorios, d.causa], ["territorio", ["La Candelaria"], true]);
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
  const s = sanear({ intencion: "borrar_todo", territorios: ["<script>", "Manrique", "Manrique", "Robledo", "Popular"], causa: "si" });
  assert.deepEqual(s, { intencion: "fuera_de_alcance", territorios: ["Manrique", "Robledo"], causa: false });
});

console.log(`\n${ok}/8 pruebas OK`);
