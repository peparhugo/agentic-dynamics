/**
 * The run_workflow tool's REAL entry point (Unit D repairs) — driven with an injected shell.
 *
 * The reviewer's requirement: the next test must exercise the actual tool entry point, not
 * only the helper functions. `setCommandRunner` replaces the tool's shell for these tests;
 * the production path uses the same code with Bun.spawn.
 */
import { expect, mock, test } from "bun:test"
import path from "node:path"

function chainable(): Record<string, unknown> {
  const node: Record<string, unknown> = {}
  for (const method of ["optional", "default", "describe"]) node[method] = () => node
  return node
}
mock.module("@opencode-ai/plugin", () => ({
  tool: Object.assign((definition: unknown) => definition, {
    schema: {
      string: chainable, number: chainable, boolean: chainable,
      enum: chainable, array: chainable, object: chainable,
    },
  }),
}))

const { default: toolDef, setCommandRunner } = await import("../../.opencode/tools/run_workflow")

const REPO = path.resolve(import.meta.dir, "..", "..")
const BINDING_ID = "a".repeat(64)

type Call = { args: string[]; stdin?: string }

function fakeShell(handlers: Record<string, (args: string[], stdin?: string) => { stdout: string; exitCode?: number }>) {
  const calls: Call[] = []
  const runner = async (args: string[], _cwd: string, stdin?: string) => {
    calls.push({ args, stdin })
    const key = args.some((a) => a.endsWith("session_open.py"))
      ? "session_open"
      : args.some((a) => a.endsWith("spawn_wrapper.py"))
        ? "validate"
        : args.some((a) => a.endsWith("fleet_manager.py"))
          ? "submit"
          : args.some((a) => a.endsWith("run_workflow.py"))
            ? "run"
            : args.includes("-c")
              ? "digest"
              : "other"
    const handler = handlers[key]
    if (!handler) return { stdout: "", stderr: `no fake for ${key}`, exitCode: 1 }
    const result = handler(args, stdin)
    return { stdout: result.stdout, stderr: "", exitCode: result.exitCode ?? 0 }
  }
  return { runner, calls }
}

function ctx(agent: string) {
  return { sessionID: "ses_tool", agent, directory: REPO, worktree: REPO }
}

function toolArgs(overrides: Record<string, unknown> = {}) {
  return {
    spec: "workflows/repository/fleet_job_submission.yaml",
    goal: "g",
    model: "anthropic/claude-sonnet-5",
    workdir: "/tmp/wt_tool_entry",
    thinking_effort: "high",
    thinking_budget_tokens: 0,
    output_token_limit: 0,
    timeout_min: 30,
    no_commit: false,
    resume: false,
    orchestrator: false,
    ...overrides,
  }
}

const FOUND_BINDING = JSON.stringify({
  schema: "session-binding/v1",
  status: "found",
  knowledge_id: BINDING_ID,
  binding: { context_version: 1 },
})

test("a bound AIO in-process run refuses when the REAL validator reports CLOSE", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    validate: () => ({
      stdout: JSON.stringify({
        ok: false,
        errors: ["submit: AIO session budget verdict is CLOSE — new consequential work is blocked"],
      }),
      exitCode: 2,
    }),
    run: () => ({ stdout: "SHOULD NOT RUN" }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(toolArgs(), ctx("aio-control"))
    expect(result.output).toContain("refused")
    expect(result.output).toContain("CLOSE")
    // ZERO executor calls: the local runner never ran.
    expect(calls.some((c) => c.args.some((a) => a.endsWith("run_workflow.py")))).toBe(false)
    // The validator was asked with the real gate flags.
    const validator = calls.find((c) => c.args.some((a) => a.endsWith("spawn_wrapper.py")))
    expect(validator?.args).toContain("--strict-aio-budget")
    expect(validator?.args).toContain("--require-deterministic")
  } finally {
    setCommandRunner(null)
  }
})

test("a verified deterministic AIO run proceeds to local execution", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    validate: () => ({ stdout: JSON.stringify({ ok: true, errors: [] }) }),
    run: () => ({ stdout: "workflow completed" }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(toolArgs(), ctx("aio-control"))
    expect(result.output).toContain("workflow completed")
    expect(calls.some((c) => c.args.some((a) => a.endsWith("run_workflow.py")))).toBe(true)
  } finally {
    setCommandRunner(null)
  }
})

test("a worker skips the AIO gate and keeps the local path", async () => {
  const { runner, calls } = fakeShell({
    run: () => ({ stdout: "worker run done" }),
    session_open: () => ({ stdout: FOUND_BINDING }),
    validate: () => ({ stdout: JSON.stringify({ ok: false, errors: ["unexpected"] }) }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(toolArgs(), ctx("build"))
    expect(result.output).toContain("worker run done")
    expect(calls.some((c) => c.args.some((a) => a.endsWith("session_open.py")))).toBe(false)
    expect(calls.some((c) => c.args.some((a) => a.endsWith("spawn_wrapper.py")))).toBe(false)
  } finally {
    setCommandRunner(null)
  }
})

test("the durable AIO submit carries the identity flags and no --project", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    digest: () => ({ stdout: "b".repeat(64) }),
    submit: () => ({ stdout: "fleet:commands <- {}\nfleet:jobs[abc123] <- launching" }),
  })
  setCommandRunner(runner)
  try {
    await (toolDef as any).execute(toolArgs({ orchestrator: true }), ctx("aio-control"))
    const submit = calls.find((c) => c.args.some((a) => a.endsWith("fleet_manager.py")))
    expect(submit).toBeDefined()
    expect(submit!.args).toContain("--aio-session-id")
    expect(submit!.args).toContain("ses_tool")
    expect(submit!.args).toContain("--binding-id")
    expect(submit!.args).toContain(BINDING_ID)
    expect(submit!.args).not.toContain("--project")
    expect(calls.some((c) => c.args.some((a) => a.endsWith("run_workflow.py")))).toBe(false)
  } finally {
    setCommandRunner(null)
  }
})
