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

test("a bound AIO in-process run refuses on a validator refusal, without the retired capacity flag", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    validate: () => ({
      stdout: JSON.stringify({
        ok: false,
        errors: ["submit: no durable AIO binding for session 'ses_tool' (status missing) — an unbound AIO submit is refused"],
      }),
      exitCode: 2,
    }),
    run: () => ({ stdout: "SHOULD NOT RUN" }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(toolArgs(), ctx("aio-control"))
    expect(result.output).toContain("refused")
    // ZERO executor calls: the local runner never ran.
    expect(calls.some((c) => c.args.some((a) => a.endsWith("run_workflow.py")))).toBe(false)
    // The validator was asked with the real gate flag — and NOT the retired capacity flag
    // (2026-09-16 policy: conversation capacity is advisory, never an admission refusal).
    const validator = calls.find((c) => c.args.some((a) => a.endsWith("spawn_wrapper.py")))
    expect(validator?.args).toContain("--require-deterministic")
    expect(validator?.args).not.toContain("--strict-aio-budget")
  } finally {
    setCommandRunner(null)
  }
})

test("a capacity advisory rides the result and never refuses", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    validate: () => ({
      stdout: JSON.stringify({
        ok: true,
        errors: [],
        aio_capacity: {
          verdict: "COMPACT",
          reason: "at the native boundary",
          measured: true,
          advisory: true,
        },
      }),
    }),
    run: () => ({ stdout: "workflow completed" }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(toolArgs(), ctx("aio-control"))
    expect(result.output).toContain("workflow completed")
    expect((result.metadata as any).aio_capacity?.verdict).toBe("COMPACT")
    expect(calls.some((c) => c.args.some((a) => a.endsWith("run_workflow.py")))).toBe(true)
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

/** The fleet-submit/v1 document the manager emits (the durable interface, never a log line). */
function fleetSubmit(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    schema: "fleet-submit/v1",
    job_id: "abc123",
    reconciled: false,
    status: "launching",
    request_key: "",
    spec: "workflows/repository/fleet_job_submission.yaml",
    spec_sha256: "b".repeat(64),
    goal: "g",
    model: "openai/gpt-6-astra",
    workdir: "/tmp/wt_tool_entry",
    resume: false,
    parent_run_id: "",
    prep_note: "",
    ...overrides,
  })
}

test("the durable AIO submit carries the identity flags and no --project", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    digest: () => ({ stdout: "b".repeat(64) }),
    submit: () => ({ stdout: fleetSubmit() }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(toolArgs({ orchestrator: true }), ctx("aio-control"))
    const submit = calls.find((c) => c.args.some((a) => a.endsWith("fleet_manager.py")))
    expect(submit).toBeDefined()
    expect(submit!.args).toContain("--aio-session-id")
    expect(submit!.args).toContain("ses_tool")
    expect(submit!.args).toContain("--binding-id")
    expect(submit!.args).toContain(BINDING_ID)
    expect(submit!.args).not.toContain("--project")
    expect(submit!.args).toContain("--workdir")
    // The structured result is the requested interface.
    expect(submit!.args).toContain("--json")
    // The ordinary path is RETRY-SAFE by default: the fleet derives and retains the request
    // identity before sending — the AIO does not have to remember anything.
    expect(submit!.args).toContain("--retry-safe")
    expect(submit!.args).not.toContain("--request-key")
    expect((result.metadata as any).reconciled).toBe(false)
    expect((result.metadata as any).retry_safe).toBe(true)
    expect((result.metadata as any).job_id).toBe("abc123")
    expect((result.metadata as any).status).toBe("launching")
    expect(calls.some((c) => c.args.some((a) => a.endsWith("run_workflow.py")))).toBe(false)
  } finally {
    setCommandRunner(null)
  }
})

test("an omitted workdir rides through — the fleet prepares the workspace", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    digest: () => ({ stdout: "b".repeat(64) }),
    submit: () => ({
      stdout: fleetSubmit({
        workdir: "/tmp/wtroot/wt_spec_1234abcd",
        prep_note: "workspace prepared: /tmp/wtroot/wt_spec_1234abcd (branch wt_spec_1234abcd, base main)",
      }),
    }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(
      toolArgs({ orchestrator: true, workdir: undefined }), ctx("aio-control"),
    )
    const submit = calls.find((c) => c.args.some((a) => a.endsWith("fleet_manager.py")))
    expect(submit!.args).not.toContain("--workdir")
    expect((result.metadata as any).workdir).toBe("/tmp/wtroot/wt_spec_1234abcd")
    expect((result.metadata as any).prep_note).toContain("workspace prepared")
    expect(result.output).toContain("workspace prepared")
  } finally {
    setCommandRunner(null)
  }
})

test("an in-process run without a workdir refuses before execution", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    run: () => ({ stdout: "SHOULD NOT RUN" }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(
      toolArgs({ orchestrator: false, workdir: undefined }), ctx("aio-control"),
    )
    expect(result.output).toContain("explicit workdir")
    expect(calls.some((c) => c.args.some((a) => a.endsWith("run_workflow.py")))).toBe(false)
  } finally {
    setCommandRunner(null)
  }
})

test("the ordinary path surfaces the fleet-derived request key for retention", async () => {
  const DERIVED = "auto:" + "c".repeat(32)
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    digest: () => ({ stdout: "b".repeat(64) }),
    submit: () => ({ stdout: fleetSubmit({ request_key: DERIVED }) }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(toolArgs({ orchestrator: true }), ctx("aio-control"))
    const submit = calls.find((c) => c.args.some((a) => a.endsWith("fleet_manager.py")))
    expect(submit!.args).toContain("--retry-safe")
    // The effective (derived) key is echoed so a lost-response retry can reuse it verbatim.
    expect((result.metadata as any).effective_request_key).toBe(DERIVED)
    expect(result.output).toContain(DERIVED)
  } finally {
    setCommandRunner(null)
  }
})

test("a caller-stable request key forwards and a reconciled response is marked", async () => {
  const { runner, calls } = fakeShell({
    session_open: () => ({ stdout: FOUND_BINDING }),
    digest: () => ({ stdout: "b".repeat(64) }),
    submit: () => ({
      stdout: fleetSubmit({ reconciled: true, status: "launching", request_key: "req-9" }),
    }),
  })
  setCommandRunner(runner)
  try {
    const result = await (toolDef as any).execute(
      toolArgs({ orchestrator: true, request_key: "req-9" }), ctx("aio-control"),
    )
    const submit = calls.find((c) => c.args.some((a) => a.endsWith("fleet_manager.py")))
    expect(submit!.args).toContain("--request-key")
    expect(submit!.args).toContain("req-9")
    // An EXPLICIT key wins over the retry-safe default.
    expect(submit!.args).not.toContain("--retry-safe")
    // A reconciled retry says so — nothing new was queued and the same identity carries on.
    expect(result.output).toContain("RECONCILED")
    expect((result.metadata as any).reconciled).toBe(true)
    expect((result.metadata as any).request_key).toBe("req-9")
    expect((result.metadata as any).job_id).toBe("abc123")
  } finally {
    setCommandRunner(null)
  }
})
