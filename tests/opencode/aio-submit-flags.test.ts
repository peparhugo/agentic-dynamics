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
    "--binding-context-version", "3",
  ])
})

test("the AUTHORIZATION identity is preferred over the record id and context version", () => {
  // Round-9/10: the gate checks the authorization identity — stable across progress
  // recording — never the content-addressed record id / context version.
  const result = aioSubmitFlags("ses_aio", "aio-control", {
    status: "found",
    knowledge_id: "b".repeat(64),
    authorization_id: BINDING_ID,
    authorization_version: 5,
    binding: { context_version: 9 },
  })
  expect(result.refuse).toBe("")
  expect(result.flags).toEqual([
    "--aio-session-id", "ses_aio",
    "--aio-agent", "aio-control",
    "--binding-id", BINDING_ID,
    "--task-revision", "5",
    "--binding-context-version", "9",
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
  expect(noId.refuse).toContain("no authorization identity/epoch")
  const noRevision = aioSubmitFlags("ses_x", "aio-control", {
    status: "found", knowledge_id: BINDING_ID, binding: { context_version: 0 },
  })
  expect(noRevision.refuse).toContain("no authorization identity/epoch")
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

test("the coordinator gate parses the durable read; the project is never a tool flag", () => {
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
  // Reviewer repair: the manager's parser never accepted --project; the backend resolves the
  // project from the durable binding. The tool must not emit an unparseable flag.
  expect(bound.flags).not.toContain("--project")
})

test("the native tool's emitted flags parse in the REAL CLI", () => {
  // THE connection the helper tests missed: the tool's argv → the actual fleet_manager parser,
  // with the manager's Redis connection faked inside the snippet.
  const { execFileSync } = require("node:child_process")
  const path = require("node:path")
  const repo = path.resolve(import.meta.dir, "..", "..")
  const snippet = [
    "import json, sys",
    "sys.path.insert(0, 'scripts/fleet')",
    "import fleet_manager as fm",
    "class R:",
    "    def __init__(self):",
    "        self.lists = {}",
    "        self.hashes = {}",
    "    def lpush(self, k, v):",
    "        self.lists.setdefault(k, []).insert(0, v)",
    "    def hset(self, k, mapping=None, **kw):",
    "        self.hashes.setdefault(k, {}).update(mapping or {})",
    "    def hget(self, k, f):",
    "        return self.hashes.get(k, {}).get(f)",
    "    def hvals(self, k):",
    "        return list(self.hashes.get(k, {}).values())",
    "r = R()",
    "fm._connect = lambda: r",
    "rc = fm.main(sys.argv[1:])",
    "queued = [json.loads(x) for x in r.lists.get(fm.COMMANDS_KEY, [])]",
    "print(json.dumps({'rc': rc, 'queued': queued}))",
  ].join("\n")
  const emitted = aioSubmitFlags("ses_a", "aio-control", {
    status: "found", knowledge_id: BINDING_ID, binding: { context_version: 2 },
  })
  expect(emitted.refuse).toBe("")
  const argv = [
    "-c", snippet,
    "submit",
    "--spec", "workflows/repository/fleet_job_submission.yaml",
    "--goal", "g", "--model", "anthropic/claude-sonnet-5",
    "--workdir", "/tmp/wt_tool_cli_regression",
    ...emitted.flags,
  ]
  const out = execFileSync("python3", argv, { cwd: repo, encoding: "utf8" })
  const parsed = JSON.parse(out.trim().split("\n").pop() as string)
  expect(parsed.rc).toBe(0)
  expect(parsed.queued[0].actor).toBe("aio")
  expect(parsed.queued[0].aio.native_session_id).toBe("ses_a")
  expect(parsed.queued[0].aio.binding_id).toBe(BINDING_ID)
  expect(parsed.queued[0].aio.task_revision).toBe(2)
})
