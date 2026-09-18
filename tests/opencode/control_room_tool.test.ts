/**
 * The Control Room tool's F0 repairs (delivery-simplification Units 4-5): explicit base-URL
 * resolution (CONTROL_ROOM_URL > FINOPS_HOST/FINOPS_PORT > loopback default) and THREE
 * distinguishable outcomes — unavailable service, non-success response, valid data — under a
 * bounded request deadline. The existing mock pattern mirrors run_workflow_tool.test.ts.
 */
import { afterEach, expect, mock, test } from "bun:test"

function chainable(): Record<string, unknown> {
  const node: Record<string, unknown> = {}
  for (const method of ["optional", "default", "describe"]) node[method] = () => node
  return node
}
mock.module("@opencode-ai/plugin", () => ({
  tool: Object.assign((definition: unknown) => definition, {
    schema: {
      string: chainable,
      number: chainable,
      boolean: chainable,
      enum: chainable,
      array: chainable,
      object: chainable,
    },
  }),
}))

const { default: toolDef, resolveBaseUrl } = await import("../../.opencode/tools/control_room")

const originalFetch = globalThis.fetch
const savedEnv = { ...process.env }
afterEach(() => {
  globalThis.fetch = originalFetch
  process.env.CONTROL_ROOM_URL = savedEnv.CONTROL_ROOM_URL
  process.env.FINOPS_HOST = savedEnv.FINOPS_HOST
  process.env.FINOPS_PORT = savedEnv.FINOPS_PORT
})

test("resolveBaseUrl: explicit CONTROL_ROOM_URL wins, trailing slashes trimmed", () => {
  expect(resolveBaseUrl({ CONTROL_ROOM_URL: "http://100.83.229.3:8001/" })).toBe(
    "http://100.83.229.3:8001",
  )
})

test("resolveBaseUrl: FINOPS host/port compose (the portal unit's declared endpoint)", () => {
  expect(resolveBaseUrl({ FINOPS_HOST: "100.83.229.3", FINOPS_PORT: "8001" })).toBe(
    "http://100.83.229.3:8001",
  )
})

test("resolveBaseUrl: compatible loopback default", () => {
  expect(resolveBaseUrl({})).toBe("http://127.0.0.1:8000")
})

test("execute: unavailable service is a precise bounded failure, never fabricated data", async () => {
  // Hermetic: the host tool env now legitimately carries CONTROL_ROOM_URL (the F0 drop-in),
  // so this case must clear it explicitly rather than assume an ambient-free environment.
  delete process.env.CONTROL_ROOM_URL
  delete process.env.FINOPS_HOST
  delete process.env.FINOPS_PORT
  globalThis.fetch = (async () => {
    const err = new Error("connection refused")
    err.name = "TimeoutError"
    throw err
  }) as unknown as typeof fetch

  const result = (await toolDef.execute({ endpoint: "projections" })) as {
    output: string
    metadata: Record<string, unknown>
  }
  expect(result.metadata.outcome).toBe("unavailable")
  expect(result.output).toContain("http://127.0.0.1:8000/api/projections")
  expect(result.output).toContain("10000ms")
})

test("execute: non-success response carries the HTTP status", async () => {
  process.env.CONTROL_ROOM_URL = "http://portal.test:9000"
  globalThis.fetch = (async () => new Response("portal degraded", { status: 503 })) as unknown as typeof fetch

  const result = (await toolDef.execute({ endpoint: "glance" })) as {
    output: string
    metadata: Record<string, unknown>
  }
  expect(result.metadata.outcome).toBe("non-success")
  expect(result.metadata.status).toBe(503)
  expect(result.metadata.url).toBe("http://portal.test:9000/api/glance")
})

test("execute: a stalled response BODY is unavailable, not an uncaught timeout", async () => {
  process.env.CONTROL_ROOM_URL = "http://portal.test:9000"
  // Headers arrive, then the body never does: `res.text()` rejects with the deadline.
  globalThis.fetch = (async () =>
    ({
      ok: true,
      status: 200,
      text: async () => {
        const err = new Error("body stalled")
        err.name = "TimeoutError"
        throw err
      },
    }) as unknown as Response) as unknown as typeof fetch

  const result = (await toolDef.execute({ endpoint: "status" })) as {
    output: string
    metadata: Record<string, unknown>
  }
  expect(result.metadata.outcome).toBe("unavailable")
  expect(result.output).toContain("10000ms")
})

test("execute: valid data passes through from the configured base URL", async () => {
  process.env.CONTROL_ROOM_URL = "http://100.83.229.3:8001"
  let seen = ""
  globalThis.fetch = (async (input: unknown) => {
    seen = String(input)
    return new Response('{"ok":true}', { status: 200 })
  }) as unknown as typeof fetch

  const result = (await toolDef.execute({ endpoint: "status" })) as {
    output: string
    metadata: Record<string, unknown>
  }
  expect(seen).toBe("http://100.83.229.3:8001/api/status")
  expect(result.metadata.outcome).toBe("ok")
  expect(JSON.parse(result.output)).toEqual({ ok: true })
})

test("execute: the new read-only selectors exist and stay GET-only paths", async () => {
  process.env.CONTROL_ROOM_URL = "http://portal.test"
  const seen: string[] = []
  globalThis.fetch = (async (input: unknown) => {
    seen.push(String(input))
    return new Response("{}", { status: 200 })
  }) as unknown as typeof fetch

  for (const endpoint of ["matrix", "status", "flags", "routing", "design_sessions", "claude_agents", "projections", "glance", "operations"]) {
    await toolDef.execute({ endpoint })
  }
  expect(seen).toEqual([
    "http://portal.test/api/matrix",
    "http://portal.test/api/status",
    "http://portal.test/api/flags",
    "http://portal.test/api/routing",
    "http://portal.test/api/design-sessions",
    "http://portal.test/api/claude-agents",
    "http://portal.test/api/projections",
    "http://portal.test/api/glance",
    "http://portal.test/api/operations",
  ])
})
