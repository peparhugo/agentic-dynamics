/**
 * The AIO submit-identity flags (Unit D) — argv-level regression.
 *
 * The tool's `@opencode-ai/plugin` import is mocked (the package is not installed in a
 * worktree checkout); `aioSubmitFlags` is pure and carries the invariant under test: the
 * identity comes from the native session/agent + a durable binding read, never from a
 * model-supplied field.
 */
import { expect, mock, test } from "bun:test"

// A minimal zod-like schema stub: the tool module builds its args at import time.
function chainable(): Record<string, unknown> {
  const node: Record<string, unknown> = {}
  for (const method of ["optional", "default", "describe"]) {
    node[method] = () => node
  }
  return node
}
const schemaStub = {
  string: chainable, number: chainable, boolean: chainable,
  enum: chainable, array: chainable, object: chainable,
}
mock.module("@opencode-ai/plugin", () => ({
  tool: Object.assign((definition: unknown) => definition, { schema: schemaStub }),
}))

const { aioSubmitFlags, isAioAgent, toolBindingGate } = await import("../../.opencode/tools/run_workflow")

const BINDING_ID = "a".repeat(64)

test("a bound native session yields the exact identity flags", () => {
  const result = aioSubmitFlags("ses_aio", "aio-control", {
    status: "found",
    knowledge_id: BINDING_ID,
    binding: { context_version: 3 },
  })
  expect(result.refuse).toBe("")
  expect(result.flags).toEqual([
    "--aio-session-id", "ses_aio",
    "--aio-agent", "aio-control",
    "--binding-id", BINDING_ID,
    "--task-revision", "3",
  ])
})

test("an absent native session identity refuses early", () => {
  const result = aioSubmitFlags("", "aio-control", {
    status: "found",
    knowledge_id: BINDING_ID,
    binding: { context_version: 1 },
  })
  expect(result.flags).toEqual([])
  expect(result.refuse).toContain("no native session identity")
})

test("an unbound session refuses early (the backend refuses independently too)", () => {
  for (const report of [null, { status: "missing" }, { status: "store_missing" }]) {
    const result = aioSubmitFlags("ses_x", "aio-control", report as never)
    expect(result.flags).toEqual([])
    expect(result.refuse).toContain("no durable AIO binding")
  }
})

test("a binding without a record id or a positive revision refuses", () => {
  const noId = aioSubmitFlags("ses_x", "aio-control", {
    status: "found", knowledge_id: "", binding: { context_version: 1 },
  })
  expect(noId.refuse).toContain("no record id / task revision")
  const noRevision = aioSubmitFlags("ses_x", "aio-control", {
    status: "found", knowledge_id: BINDING_ID, binding: { context_version: 0 },
  })
  expect(noRevision.refuse).toContain("no record id / task revision")
})


test("a worker agent keeps its contract: no gate, no stamps", () => {
  expect(isAioAgent("build")).toBe(false)
  expect(isAioAgent("")).toBe(false)
  expect(isAioAgent("aio-control")).toBe(true)
  const result = aioSubmitFlags("ses_w", "build", null)
  expect(result.refuse).toBe("")
  expect(result.flags).toEqual([])
  // even with a found binding, a non-AIO agent is not stamped with the AIO identity
  const withBinding = aioSubmitFlags("ses_w", "build", {
    status: "found", knowledge_id: BINDING_ID, binding: { context_version: 1 },
  })
  expect(withBinding.flags).toEqual([])
})

test("the coordinator gate parses the durable read and stamps the project association", () => {
  const refused = toolBindingGate("aio-control", "ses_a", "not json")
  expect(refused.refuse).toContain("no durable AIO binding")
  const bound = toolBindingGate(
    "aio-control",
    "ses_a",
    JSON.stringify({
      status: "found",
      knowledge_id: BINDING_ID,
      binding: { context_version: 2, project: "github.com/peparhugo/agentic-dynamics" },
    }),
  )
  expect(bound.refuse).toBe("")
  expect(bound.flags).toContain("--project")
  expect(bound.flags[bound.flags.indexOf("--project") + 1]).toBe(
    "github.com/peparhugo/agentic-dynamics",
  )
})
