# Worker "interprete" (IA opcional del portal)

Interpreta la pregunta del usuario con Gemini y devuelve SOLO
`{intencion, territorios, causa}`. Las cifras las pone el motor determinista
del portal desde `knowledge_base.json`; la IA nunca escribe números.
Si el Worker falla o no tiene clave, el portal responde en modo determinista.

## Configuración (una sola vez)

Desde la terminal donde está `gh` autenticado. Los comandos leen el valor
desde un archivo o desde el teclado: no queda en el historial ni en el repo.

```bash
# 1) Token de Cloudflare (Workers Scripts:Edit + Account Settings:Read)
gh secret set CLOUDFLARE_API_TOKEN -R watabares/medellin-bienestar-datos < ~/.config/cf_token

# 2) Clave de Gemini (Google AI Studio): pégala cuando la pida y pulsa Enter
gh secret set GEMINI_API_KEY -R watabares/medellin-bienestar-datos
```

## Desplegar

Automático en cada push que cambie `worker/`. Manual:

```bash
gh workflow run worker-ia -R watabares/medellin-bienestar-datos
```

La URL del Worker aparece en el resumen del run (`https://bienestar-medellin-ia.<subdominio>.workers.dev`).

## Verificar

```bash
URL=https://bienestar-medellin-ia.<subdominio>.workers.dev
curl -s $URL/salud                                    # {"ok":true}
curl -s -X POST $URL/interpretar -H 'Origin: https://watabares.github.io' \
     -H 'Content-Type: application/json' -d '{"pregunta":"¿por qué mueren tantos en el centro?"}'
# → {"intencion":"territorio","territorios":["La Candelaria"],"causa":true,...}
```

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `403 origen no permitido` | La petición no viene del portal | Normal para curl sin `-H Origin` |
| `503 IA no configurada` | Falta `GEMINI_API_KEY` | Paso 2 y relanzar el workflow |
| `502 IA no disponible` | Modelo inexistente o cuota agotada | Cambiar `MODELO` en `wrangler.toml`; ver logs con *Workers → Logs* |
| `429` | Límite por IP (10/min) o global (30/min) | Esperar un minuto |

## Pruebas

`node worker/test.mjs` (sin red; simula Gemini). Corren también en el workflow.
