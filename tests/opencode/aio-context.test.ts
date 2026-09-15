/**
 * Native-hook tests for the AIO context plugin (Unit C).
 *
 * Run:  bun test tests/opencode/aio-context.test.ts
 *
 * The plugin's only dependency is the `session_open.py` CLI; every test injects a fake
 * command runner, so no model calls, no python, no opencode process. The tests assert the
 * hook behavior against the DEPLOYED interface shapes (opencode 1.18.15): `chat.message`
 * carries `sessionID` + resolved `output.message.agent`; `experimental.chat.system.transform`
 * carries an optional session id and an `output.system` array; `tool.execute.before`
 * carries the tool name + session id.
 */
import { describe, expect, test } from "bun:test"

import { AioContextPlugin } from "../../.opencode/plugins/aio-context"

type FakeResponse = Record<string, unknown> | undefined
type Call = { args: string[]; stdin?: string }

function sessionOf(args: string[]): string {
  const index = args.indexOf("--native-session-id")
  return index >= 0 ? args[index + 1] : ""
}

function modeOf(args: string[]): string {
  if (args.includes("--update-context")) return "update-context"
  if (args.includes("--init-store")) return "init-store"
  if (args.includes("--bind")) return "bind"
  if (args.includes("--binding")) return "binding"
  if (args.includes("--capsule")) return "capsule"
  return "unknown"
}

/** A response map + call log; `responder` may return undefined to simulate a failure. */
function fakeRunner(responder: (mode: string, args: string[]) => FakeResponse) {
  const calls: Call[] = []
  const runner = async (cmd: string[], stdin?: string) => {
    calls.push({ args: cmd, stdin })
    const payload = responder(modeOf(cmd), cmd)
    if (payload === undefined) return { code: 1, stdout: "", stderr: "boom" }
    return { code: 0, stdout: JSON.stringify(payload), stderr: "" }
  }
  return { calls, runner }
}

async function makePlugin(runner: unknown, options: Record<string, unknown> = {}) {
  return await (AioContextPlugin as unknown as (ctx: unknown, opts: unknown) => Promise<any>)(
    { directory: "/repo", worktree: "/repo" },
    { commandRunner: runner, capsuleTtlMs: 60_000, ...options },
  )
}

function message(sessionID: string, agent: string, text: string, id = "msg_1") {
  return {
    input: { sessionID, messageID: id },
    output: { message: { id, agent }, parts: [{ type: "text", text }] },
  }
}

/** A standard responder: bind succeeds, binding is found once bound, capsule names the session. */
function happyResponder(boundSessions: Set<string>) {
  return (mode: string, args: string[]): FakeResponse => {
    const session = sessionOf(args)
    if (mode === "bind") {
      boundSessions.add(session)
      return { schema: "session-binding/v1", status: "created", native_session_id: session }
    }
    if (mode === "binding") {
      return boundSessions.has(session)
        ? { schema: "session-binding/v1", status: "found", binding: { native_session_id: session } }
        : { schema: "session-binding/v1", status: "missing" }
    }
    if (mode === "capsule") {
      return boundSessions.has(session)
        ? {
            schema: "session-capsule/v1",
            capsule_status: "composed",
            capsule: { text: `CAPSULE:${session}` },
          }
        : { schema: "session-capsule/v1", capsule_status: "missing", capsule: null }
    }
    return undefined
  }
}

describe("aio-context plugin", () => {
  test("the first request and a later (post-compaction) request both receive the capsule", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    await hooks["chat.message"](...Object.values(message("ses_a", "aio-control", "do the task")))
    const first = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_a" }, first)
    // A second request (the shape a post-compaction request takes: same session, no new
    // chat.message) still receives the capsule.
    const second = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_a" }, second)

    expect(first.system).toEqual(["CAPSULE:ses_a"])
    expect(second.system).toEqual(["CAPSULE:ses_a"])
    // The capsule request is identity-scoped — never a "latest close" read.
    const capsuleCalls = calls.filter((c) => modeOf(c.args) === "capsule")
    expect(capsuleCalls.length).toBeGreaterThan(0)
    for (const call of capsuleCalls) {
      expect(sessionOf(call.args)).toBe("ses_a")
      expect(call.args).not.toContain("--slug")
    }
  })

  test("two concurrent tasks do not exchange capsules", async () => {
    const bound = new Set<string>()
    const { runner } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    await hooks["chat.message"](...Object.values(message("ses_one", "aio-control", "task one")))
    await hooks["chat.message"](...Object.values(message("ses_two", "aio-control", "task two")))
    const one = { system: [] as string[] }
    const two = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_one" }, one)
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_two" }, two)

    expect(one.system).toEqual(["CAPSULE:ses_one"])
    expect(two.system).toEqual(["CAPSULE:ses_two"])
    expect(one.system.join()).not.toContain("ses_two")
    expect(two.system.join()).not.toContain("ses_one")
  })

  test("an unrelated newer close is never requested or injected", async () => {
    // The plugin passes ONLY the bound session identity to the composer; the composer's
    // predecessor resolution is by the binding's explicit slug (Python-tested). Here we
    // assert the two properties the plugin owns: no slug/latest read, verbatim injection.
    const bound = new Set(["ses_a"])
    const { runner, calls } = fakeRunner((mode, args) => {
      if (mode === "capsule") {
        return {
          schema: "session-capsule/v1",
          capsule_status: "composed",
          // a decoy "newer close" exists in the store; the composer ignores it by construction
          capsule: { text: "predecessor: bound-task (sha abc) — no newer-close content" },
        }
      }
      return happyResponder(bound)(mode, args)
    })
    const hooks = await makePlugin(runner)
    const out = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_a" }, out)

    expect(calls.some((c) => c.args.includes("--slug"))).toBe(false)
    expect(out.system).toEqual(["predecessor: bound-task (sha abc) — no newer-close content"])
  })

  test("worker sessions receive no private coordinator capsule", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    await hooks["chat.message"](...Object.values(message("ses_w", "build", "implement it")))
    const out = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_w" }, out)

    expect(out.system).toEqual([])
    expect(calls.some((c) => modeOf(c.args) === "capsule")).toBe(false)
    expect(calls.some((c) => modeOf(c.args) === "bind")).toBe(false)
  })

  test("a restart rehydrates the binding from the durable store", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const first = await makePlugin(runner)
    await first["chat.message"](...Object.values(message("ses_r", "aio-control", "task")))
    const before = calls.filter((c) => modeOf(c.args) === "capsule").length

    // A fresh plugin instance (a coordinator restart): no process-local map survives.
    const second = await makePlugin(runner)
    const out = { system: [] as string[] }
    await second["experimental.chat.system.transform"]({ sessionID: "ses_r" }, out)

    expect(out.system).toEqual(["CAPSULE:ses_r"])
    expect(calls.filter((c) => modeOf(c.args) === "capsule").length).toBeGreaterThan(before)
  })

  test("a later continue-message never rebuilds the binding, and rebinding is idempotent", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    await hooks["chat.message"](...Object.values(message("ses_c", "aio-control", "ORIGINAL", "m1")))
    await hooks["chat.message"](...Object.values(message("ses_c", "aio-control", "continue", "m2")))
    await hooks["chat.message"](...Object.values(message("ses_c", "aio-control", "continue again", "m3")))

    const binds = calls.filter((c) => modeOf(c.args) === "bind")
    expect(binds.length).toBe(1) // the original request was bound exactly once
    expect(binds[0].stdin).toContain("ORIGINAL")
  })

  test("missing store differs from a missing binding, and a dependency failure is explicit", async () => {
    const { runner } = fakeRunner((mode, args) => {
      if (mode !== "capsule") return undefined
      const session = sessionOf(args)
      if (session === "ses_store") {
        return { schema: "session-binding/v1", status: "store_missing", capsule_status: "store_missing" }
      }
      if (session === "ses_bad") return undefined // crash/timeout: code 1, no JSON
      return { schema: "session-binding/v1", status: "missing", capsule_status: "missing" }
    })
    const hooks = await makePlugin(runner)

    for (const session of ["ses_store", "ses_bad", "ses_missing"]) {
      const out = { system: [] as string[] }
      await hooks["experimental.chat.system.transform"]({ sessionID: session }, out)
      expect(out.system).toEqual([]) // never a fabricated capsule, never a crash
    }
  })

  test("the plugin's own size bound truncates explicitly", async () => {
    const { runner } = fakeRunner((mode) =>
      mode === "capsule"
        ? {
            schema: "session-capsule/v1",
            capsule_status: "composed",
            capsule: { text: "x".repeat(5000) },
          }
        : undefined,
    )
    const hooks = await makePlugin(runner, { capsuleMaxChars: 100 })
    const out = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_big" }, out)

    const injected = out.system.join()
    // The plugin floors a tiny custom limit at MIN_CAPSULE_CHARS (600) so the protected
    // tail can never be cut; the oversized capsule is still truncated explicitly.
    expect(injected.length).toBeLessThan(750)
    expect(injected.length).toBeGreaterThan(600)
    expect(injected).toContain("[capsule truncated by the plugin:")
  })

  test("a wrong/reused profile is observed honestly: build never binds, a changed agent does", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    await hooks["chat.message"](...Object.values(message("ses_x", "build", "a worker turn", "m1")))
    expect(calls.some((c) => modeOf(c.args) === "bind")).toBe(false)

    // The SAME session reused as the coordinator: the observed agent updates, and the bind
    // records the agent honestly.
    await hooks["chat.message"](...Object.values(message("ses_x", "aio-control", "now the AIO", "m2")))
    const bind = calls.find((c) => modeOf(c.args) === "bind")
    expect(bind).toBeDefined()
    expect(bind!.args[bind!.args.indexOf("--agent") + 1]).toBe("aio-control")
  })

  test("an unbound AIO submit refuses early; a bound AIO and a worker do not", async () => {
    const { runner } = fakeRunner((mode, args) => {
      const session = sessionOf(args)
      if (mode === "binding") {
        return session === "ses_bound"
          ? { schema: "session-binding/v1", status: "found", binding: { native_session_id: session } }
          : { schema: "session-binding/v1", status: "missing" }
      }
      if (mode === "bind") {
        return session === "ses_bound"
          ? { schema: "session-binding/v1", status: "existing" }
          : undefined
      }
      return undefined
    })
    const hooks = await makePlugin(runner)

    await hooks["chat.message"](...Object.values(message("ses_unbound", "aio-control", "task")))
    await expect(
      hooks["tool.execute.before"]({ tool: "run_workflow", sessionID: "ses_unbound", callID: "c1" }, { args: {} }),
    ).rejects.toThrow(/unbound AIO session/)

    await hooks["chat.message"](...Object.values(message("ses_bound", "aio-control", "task")))
    await expect(
      hooks["tool.execute.before"]({ tool: "run_workflow", sessionID: "ses_bound", callID: "c2" }, { args: {} }),
    ).resolves.toBeUndefined()

    await hooks["chat.message"](...Object.values(message("ses_worker", "build", "task")))
    await expect(
      hooks["tool.execute.before"]({ tool: "run_workflow", sessionID: "ses_worker", callID: "c3" }, { args: {} }),
    ).resolves.toBeUndefined()
  })

  test("auxiliary calls without identity receive nothing", async () => {
    const { runner, calls } = fakeRunner(() => {
      throw new Error("the composer must not run for an identity-less auxiliary call")
    })
    const hooks = await makePlugin(runner)
    const out = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({}, out)
    expect(out.system).toEqual([])
    expect(calls.length).toBe(0)
  })
})

// ── Unit C repairs: handoff attachment, versioned updates, explicit unavailability ──────────

import { execFileSync } from "node:child_process"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import path from "node:path"

const REPO = path.resolve(import.meta.dir, "..", "..")

function tmpDir(prefix: string): string {
  return mkdtempSync(path.join(tmpdir(), prefix))
}

function writeTaskContext(projectDir: string, context: Record<string, unknown>) {
  mkdirSync(path.join(projectDir, ".opencode"), { recursive: true })
  writeFileSync(
    path.join(projectDir, ".opencode", "aio-task-context.json"),
    JSON.stringify(context),
  )
}

function makePluginAt(runner: unknown, projectDir: string, options: Record<string, unknown> = {}) {
  return (AioContextPlugin as unknown as (ctx: unknown, opts: unknown) => Promise<any>)(
    { directory: projectDir, worktree: projectDir },
    { commandRunner: runner, capsuleTtlMs: 60_000, ...options },
  )
}

function flagOf(args: string[], flag: string): string | undefined {
  const index = args.indexOf(flag)
  return index >= 0 ? args[index + 1] : undefined
}

describe("aio-context plugin — handoff attachment and versioned context", () => {
  test("the task-context attachment reaches the binding call (predecessor, findings, acceptance, work unit)", async () => {
    const project = tmpDir("aio-project-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_ctx",
        task: "unit-c-integration",
        predecessor_slug: "bound-handoff",
        knowledge_ids: ["f".repeat(64)],
        acceptance: "tests green; PR merged",
        acceptance_source: "raw",
        project: "integration-project",
        source_revision: "deadbeef",
        work_unit: "attach the handoff",
        next_action: "verify the capsule",
        context_version: 1,
      })
      const bound = new Set<string>()
      const { runner, calls } = fakeRunner(happyResponder(bound))
      const hooks = await makePluginAt(runner, project)

      await hooks["chat.message"](...Object.values(message("ses_ctx", "aio-control", "run the unit")))

      const bind = calls.find((c) => modeOf(c.args) === "bind")
      expect(bind).toBeDefined()
      expect(flagOf(bind!.args, "--task")).toBe("unit-c-integration")
      expect(flagOf(bind!.args, "--predecessor-slug")).toBe("bound-handoff")
      expect(flagOf(bind!.args, "--knowledge-id")).toBe("f".repeat(64))
      expect(flagOf(bind!.args, "--acceptance")).toBe("tests green; PR merged")
      expect(flagOf(bind!.args, "--project")).toBe("integration-project")
      expect(flagOf(bind!.args, "--source-revision")).toBe("deadbeef")
      expect(flagOf(bind!.args, "--work-unit")).toBe("attach the handoff")
      expect(flagOf(bind!.args, "--context-version")).toBe("1")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("a higher context_version triggers an explicit versioned update", async () => {
    const project = tmpDir("aio-project-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_up", task: "t", context_version: 1, work_unit: "v1 work",
      })
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return {
            schema: "session-binding/v1", status: "created",
            binding: { native_session_id: sessionOf(args), context_version: 1 },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAP" } }
        }
        if (mode === "binding") {
          return { schema: "session-binding/v1", status: "found", binding: { native_session_id: sessionOf(args) } }
        }
        return undefined
      })
      const hooks = await makePluginAt(runner, project)
      await hooks["chat.message"](...Object.values(message("ses_up", "aio-control", "start")))

      writeTaskContext(project, {
        native_session_id: "ses_up", task: "t", context_version: 2, work_unit: "v2 work",
      })
      await hooks["chat.message"](...Object.values(message("ses_up", "aio-control", "continue")))

      const update = calls.find((c) => modeOf(c.args) === "update-context")
      expect(update).toBeDefined()
      expect(flagOf(update!.args, "--expected-version")).toBe("1")
      expect(flagOf(update!.args, "--work-unit")).toBe("v2 work")
      // The original request is never in an update call.
      expect(update!.args).not.toContain("--request-file")
      expect(update!.args).not.toContain("--request")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("a dependency failure injects an explicit unavailable notice for the AIO session", async () => {
    const { runner } = fakeRunner((mode, args) => {
      if (mode === "bind") {
        return { schema: "session-binding/v1", status: "store_missing", warnings: ["root absent"] }
      }
      if (mode === "capsule") {
        return { schema: "session-capsule/v1", capsule_status: "store_missing", warnings: ["root absent"] }
      }
      return undefined
    })
    const hooks = await makePlugin(runner)
    const context = message("ses_fail", "aio-control", "do it")
    await hooks["chat.message"](...Object.values(context))
    const out = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_fail" }, out)
    expect(out.system.join()).toContain("[aio-context] capsule unavailable:")
    expect(out.system.join()).toContain("store_missing")

    // A worker session gets no such notice (it is not the AIO boundary).
    await hooks["chat.message"](...Object.values(message("ses_worker2", "build", "task")))
    const workerOut = { system: [] as string[] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "ses_worker2" }, workerOut)
    expect(workerOut.system).toEqual([])
  })

  test("the REAL runner enforces its deadline and surfaces the timeout", async () => {
    const dir = tmpDir("aio-hang-")
    try {
      const hang = path.join(dir, "hang.sh")
      writeFileSync(hang, "#!/bin/bash\nsleep 30\n")
      const hooks = await (AioContextPlugin as unknown as (ctx: unknown, opts: unknown) => Promise<any>)(
        { directory: dir, worktree: dir },
        { python: "bash", sessionOpen: hang, commandTimeoutMs: 300, capsuleTtlMs: 0 },
      )
      await hooks["chat.message"](...Object.values(message("ses_hang", "aio-control", "task")))
      const out = { system: [] as string[] }
      await hooks["experimental.chat.system.transform"]({ sessionID: "ses_hang" }, out)
      expect(out.system.join()).toContain("[aio-context] capsule unavailable:")
      expect(out.system.join()).toContain("timed out after 300ms")
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })
})

describe("aio-context plugin — full native path (real CLI, temporary knowledge store)", () => {
  test("a selected finding and predecessor reach the injected system text", async () => {
    const root = tmpDir("aio-integration-")
    const store = path.join(root, "kb")
    const project = path.join(root, "project")
    const findingId = "a".repeat(64)
    const python = "python3"
    let previousPublish: string | undefined
    try {
      mkdirSync(store, { recursive: true })
      mkdirSync(project, { recursive: true })
      previousPublish = process.env.FINOPS_AIO_BINDING_PUBLISH
      // The scratch store must not publish synthetic binding events to the live KB stream.
      process.env.FINOPS_AIO_BINDING_PUBLISH = "0"

      // Seed the predecessor close through the REAL writer (isolated store, fake stream).
      const seed = [
        "import sys",
        `sys.path.insert(0, ${JSON.stringify(path.join(REPO, "src"))})`,
        "from agentic_dynamics.knowledge import session_ingestion as si",
        "class R:",
        "    def __init__(self):",
        "        self.h = {}",
        "        self.n = 0",
        "    def hset(self, key, field, value):",
        "        self.h[field] = value",
        "    def hget(self, key, field):",
        "        return self.h.get(field)",
        "    def xadd(self, stream, payload):",
        "        self.n += 1",
        "        return f'1-{self.n}'",
        "r = R()",
        "res = si.close_session({",
        "    'session_date': '2026-09-14',",
        "    'slug': 'c-seeded-predecessor',",
        "    'waves_run': ['seeded wave'],",
        "    'merged': [],",
        "    'parked': [],",
        "    'open_threads': ['seeded open thread'],",
        "    'self_notes': 'seeded notes',",
        `}, artifact_dir=__import__('pathlib').Path(${JSON.stringify(store)}), connect_fn=lambda: r)`,
        "print(res.status)",
      ].join("\n")
      const seeded = execFileSync(python, ["-c", seed], { encoding: "utf-8" })
      expect(seeded.trim()).toBe("closed")

      // Seed the selected FINDING record (its actual constraint is what must arrive).
      writeFileSync(
        path.join(store, `${findingId}.json`),
        JSON.stringify({
          text: "CONSTRAINT-FROM-FINDING: never deploy on Fridays",
          source_type: "finding",
          extractor_version: "measured-finding/v1",
          authority: "measured",
          evidence_class: "[M]",
        }),
      )

      // The explicit handoff attachment: predecessor + finding + acceptance ending in a
      // controlling constraint (the reviewer's NEVER DEPLOY shape).
      writeTaskContext(project, {
        native_session_id: "ses_integration",
        task: "unit-c-integration",
        predecessor_slug: "c-seeded-predecessor",
        knowledge_ids: [findingId],
        acceptance:
          "Requirement: keep the system stable. ".repeat(120) +
          "Finally: NEVER DEPLOY IN PRODUCTION on Fridays.",
        acceptance_source: "raw",
        project: "integration-project",
        source_revision: "deadbeef",
        work_unit: "hook → CLI → store integration",
        next_action: "assert the injected constraint",
        context_version: 1,
      })

      // The REAL path: the plugin's production runner spawns the REAL CLI against the
      // temporary store — no mocks anywhere between the hook and the injected text.
      const hooks = await (AioContextPlugin as unknown as (ctx: unknown, opts: unknown) => Promise<any>)(
        { directory: project, worktree: project },
        {
          python,
          sessionOpen: path.join(REPO, "scripts", "session_open.py"),
          artifactDir: store,
          commandTimeoutMs: 30_000,
          capsuleTtlMs: 0,
        },
      )
      await hooks["chat.message"](
        ...Object.values(message("ses_integration", "aio-control", "Execute Unit C repairs.")),
      )
      const out = { system: [] as string[] }
      await hooks["experimental.chat.system.transform"]({ sessionID: "ses_integration" }, out)
      const injected = out.system.join("\n")

      expect(injected).toContain("CONSTRAINT-FROM-FINDING: never deploy on Fridays")
      expect(injected).toContain("NEVER DEPLOY IN PRODUCTION")
      expect(injected).toContain("c-seeded-predecessor")
      expect(injected).toContain("seeded open thread")
      expect(injected).toContain("unit-c-integration")
      expect(injected).toContain("work unit: hook → CLI → store integration")
      expect(injected).toContain("session budget:")
      expect(injected).toContain("next action: assert the injected constraint")
    } finally {
      if (previousPublish === undefined) delete process.env.FINOPS_AIO_BINDING_PUBLISH
      else process.env.FINOPS_AIO_BINDING_PUBLISH = previousPublish
      rmSync(root, { recursive: true, force: true })
    }
  }, 60_000)
})

describe("aio-context plugin — handoff selection by session (reviewer repair)", () => {
  test("two sessions in the same project never exchange handoffs across interleaved updates", async () => {
    const project = tmpDir("aio-two-")
    try {
      // A's own attachment.
      writeTaskContext(project, {
        native_session_id: "ses_A", task: "task-A", predecessor_slug: "pred-A",
        acceptance: "A acceptance", context_version: 1,
      })
      const bound = new Set<string>()
      const { runner, calls } = fakeRunner((mode, args) => {
        const session = sessionOf(args)
        if (mode === "bind") {
          bound.add(session)
          return {
            schema: "session-binding/v1", status: "created",
            binding: {
              native_session_id: session, context_version: 1,
              task_identity: session === "ses_B" ? "task-B" : "task-A", project: "",
            },
          }
        }
        if (mode === "binding") {
          return bound.has(session)
            ? { schema: "session-binding/v1", status: "found", binding: { native_session_id: session } }
            : { schema: "session-binding/v1", status: "missing" }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: `CAPSULE:${session}` } }
        }
        if (mode === "update-context") {
          return {
            schema: "session-binding/v1", status: "updated",
            binding: { native_session_id: session, context_version: 2, task_identity: "task-B", project: "" },
          }
        }
        return undefined
      })
      const hooks = await makePluginAt(runner, project)

      await hooks["chat.message"](...Object.values(message("ses_A", "aio-control", "start A")))
      const aBind = calls.find((c) => modeOf(c.args) === "bind")!
      expect(flagOf(aBind.args, "--predecessor-slug")).toBe("pred-A")

      // B's attachment replaces the SAME file path (one file, two sessions in one project).
      writeTaskContext(project, {
        native_session_id: "ses_B", task: "task-B", predecessor_slug: "pred-B",
        acceptance: "B acceptance", context_version: 1,
      })
      await hooks["chat.message"](...Object.values(message("ses_B", "aio-control", "start B")))
      const bBind = calls.filter((c) => modeOf(c.args) === "bind").find((c) => sessionOf(c.args) === "ses_B")!
      expect(flagOf(bBind.args, "--predecessor-slug")).toBe("pred-B")

      // B's context updates to v2 while A continues.
      writeTaskContext(project, {
        native_session_id: "ses_B", task: "task-B", work_unit: "B v2", context_version: 2,
      })
      await hooks["chat.message"](...Object.values(message("ses_A", "aio-control", "continue A")))
      const updatesForA = calls.filter(
        (c) => modeOf(c.args) === "update-context" && sessionOf(c.args) === "ses_A",
      )
      expect(updatesForA.length).toBe(0) // B's update never reaches A

      await hooks["chat.message"](...Object.values(message("ses_B", "aio-control", "continue B")))
      const updatesForB = calls.filter(
        (c) => modeOf(c.args) === "update-context" && sessionOf(c.args) === "ses_B",
      )
      expect(updatesForB.length).toBe(1)
      expect(flagOf(updatesForB[0].args, "--expected-version")).toBe("1")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("a rejected context update is surfaced alongside the retained capsule, then cleared", async () => {
    const project = tmpDir("aio-reject-")
    let updateShouldFail = true
    try {
      writeTaskContext(project, {
        native_session_id: "ses_r", task: "t", work_unit: "v1", context_version: 1,
      })
      const { runner } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return {
            schema: "session-binding/v1", status: "created",
            binding: { native_session_id: sessionOf(args), context_version: 1, task_identity: "t", project: "" },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          if (updateShouldFail) return undefined // the CLI refused (e.g. bad acceptance)
          return {
            schema: "session-binding/v1", status: "updated",
            binding: { native_session_id: sessionOf(args), context_version: 2, task_identity: "t", project: "" },
          }
        }
        return undefined
      })
      const hooks = await makePluginAt(runner, project)
      await hooks["chat.message"](...Object.values(message("ses_r", "aio-control", "start")))

      writeTaskContext(project, {
        native_session_id: "ses_r", task: "t", work_unit: "v2", context_version: 2,
      })
      await hooks["chat.message"](...Object.values(message("ses_r", "aio-control", "continue")))
      const failed = { system: [] as string[] }
      await hooks["experimental.chat.system.transform"]({ sessionID: "ses_r" }, failed)
      expect(failed.system.join()).toContain("CAPSULE")
      expect(failed.system.join()).toContain("context update failed")
      expect(failed.system.join()).toContain("context version 1 remains active")

      // A second request within the cache lifetime must warn TOO (reviewer repair).
      const cachedRequest = { system: [] as string[] }
      await hooks["experimental.chat.system.transform"]({ sessionID: "ses_r" }, cachedRequest)
      expect(cachedRequest.system.join()).toContain("CAPSULE")
      expect(cachedRequest.system.join()).toContain("context version 1 remains active")

      // Reconciliation: the same update now succeeds — the notice clears.
      updateShouldFail = false
      await hooks["chat.message"](...Object.values(message("ses_r", "aio-control", "continue again")))
      const recovered = { system: [] as string[] }
      await hooks["experimental.chat.system.transform"]({ sessionID: "ses_r" }, recovered)
      expect(recovered.system.join()).toContain("CAPSULE")
      expect(recovered.system.join()).not.toContain("context update failed")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("two fresh sessions reading the same untargeted file inherit nothing", async () => {
    const project = tmpDir("aio-unref-")
    try {
      // No native_session_id, no bound identity to compare a task reference against: an
      // initial handoff cannot be validated, so NEITHER fresh session adopts it.
      writeTaskContext(project, {
        task: "task-of-elsewhere",
        predecessor_slug: "pred-of-elsewhere",
        acceptance: "orphan acceptance",
        context_version: 1,
      })
      const bound = new Set<string>()
      const { runner, calls } = fakeRunner(happyResponder(bound))
      const hooks = await makePluginAt(runner, project)

      for (const session of ["ses_u1", "ses_u2"]) {
        await hooks["chat.message"](...Object.values(message(session, "aio-control", "start")))
        const bind = calls.filter((c) => modeOf(c.args) === "bind").find((c) => sessionOf(c.args) === session)!
        expect(bind.args).not.toContain("--acceptance")
        expect(bind.args).not.toContain("--predecessor-slug")
        const out = { system: [] as string[] }
        await hooks["experimental.chat.system.transform"]({ sessionID: session }, out)
        expect(out.system.join()).toContain("an initial handoff must name the native session id")
      }
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })
})
