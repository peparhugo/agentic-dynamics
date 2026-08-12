#!/usr/bin/env node
/**
 * SDK bridge — Python ↔ opencode SDK.
 *
 * Reads JSON from stdin: {prompt, model, schema?, timeout?}
 * Returns structured JSON result on stdout.
 *
 * Usage from Python:
 *   result = subprocess.run(["node", "scripts/sdk_bridge.mjs"],
 *       input=json.dumps({"prompt": "...", "model": "...", "schema": {...}}),
 *       capture_output=True, text=True, timeout=600)
 *   output = json.loads(result.stdout)
 */

import { fileURLToPath } from "node:url"
import path from "node:path"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, "..")

// Resolve SDK from .opencode/node_modules (where opencode installs it)
const sdkEntry = path.join(
  projectRoot,
  ".opencode", "node_modules", "@opencode-ai", "sdk",
  "dist", "v2", "index.js",
)
const { createOpencode } = await import(sdkEntry)

async function main() {
  let input
  try {
    const chunks = []
    for await (const chunk of process.stdin) {
      chunks.push(chunk)
    }
    input = JSON.parse(Buffer.concat(chunks).toString("utf-8"))
  } catch (err) {
    process.stderr.write(JSON.stringify({ ok: false, error: `stdin parse: ${err.message}` }))
    process.exit(1)
  }

  const { prompt, model, schema, timeout: timeoutSec } = input
  if (!prompt || !model) {
    process.stderr.write(JSON.stringify({ ok: false, error: "prompt and model are required" }))
    process.exit(1)
  }

  const [providerID, modelID] = model.split("/")
  if (!providerID || !modelID) {
    process.stderr.write(JSON.stringify({ ok: false, error: "model must be provider/model format" }))
    process.exit(1)
  }

  const msTimeout = (timeoutSec || 300) * 1000

  let server
  try {
    const opencode = await createOpencode({
      port: 0,
      timeout: msTimeout,
    })
    server = opencode.server
    const { client } = opencode

    const session = await client.session.create({
      body: { title: `bridge-${Date.now()}` },
    })

    const promptParams = {
      sessionID: session.data.id,
      model: { providerID, modelID },
      parts: [{ type: "text", text: prompt }],
    }
    if (schema) {
      promptParams.format = { type: "json_schema", schema }
    }

    const result = await client.session.prompt(promptParams)

    if (result.error) {
      process.stderr.write(JSON.stringify({
        ok: false,
        error: result.error.name || "UnknownError",
        message: result.error.message || result.error.data?.message || "server error",
        ref: result.error.data?.ref || null,
      }) + "\n")
      process.exit(1)
    }

    // Extract text from response parts
    let text = ""
    const parts = result.data?.info?.parts || result.data?.parts || []
    text = parts
      .filter((p) => p.type === "text")
      .map((p) => p.text)
      .join("\n")

    process.stdout.write(JSON.stringify({
      ok: true,
      structured: result.data?.info?.structured || result.data?.structured || null,
      text: text || null,
      cost: result.data?.info?.cost ?? result.data?.cost ?? 0,
      tokens: result.data?.info?.tokens ?? result.data?.tokens ?? null,
    }))
  } catch (err) {
    process.stderr.write(JSON.stringify({ ok: false, error: err.message }))
    process.exit(1)
  } finally {
    if (server) {
      try { server.close() } catch (_) {}
    }
  }
}

main().catch((err) => {
  process.stderr.write(JSON.stringify({ ok: false, error: err.message }))
  process.exit(1)
})
