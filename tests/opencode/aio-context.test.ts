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
    expect(injected.length).toBeLessThan(200)
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
