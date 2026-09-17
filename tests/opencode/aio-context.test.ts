/**
 * Native-hook tests for the AIO context plugin (Unit C).
 *
 * Run:  bun test tests/opencode/aio-context.test.ts
 *
 * The plugin's only dependency is the `session_open.py` CLI; every test injects a fake
 * command runner, so no model calls, no python, no opencode process. The tests assert the
 * hook behavior against the DEPLOYED interface shapes (opencode 1.18.15): `chat.message`
 * carries `sessionID` + resolved `output.message.agent` + the mutable `output.parts` the
 * runtime persists after the hook (the snapshot ATTACH); `experimental.chat.system.transform`
 * carries an optional session id and an `output.system` array; `experimental.chat.messages
 * .transform` carries `{}` + the mutable `output.messages` list (the recovery APPEND);
 * `tool.execute.before` carries the tool name + session id.
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
    // `eventsPath: null` keeps the suite hermetic; the journal test injects its own path.
    { commandRunner: runner, capsuleTtlMs: 60_000, eventsPath: null, ...options },
  )
}

function message(sessionID: string, agent: string, text: string, id = "msg_1") {
  return {
    input: { sessionID, messageID: id },
    output: { message: { id, agent }, parts: [{ type: "text", text }] },
  }
}

/** One outgoing request as the runtime assembles it: storage-derived messages (a FRESH copy
 *  each request — the runtime does not persist transformed entries) + the transform output. */
function requestMessages(sessionID: string, texts: string[]) {
  return {
    messages: texts.map((text, index) => ({
      info: { id: `msg_${index + 1}`, sessionID, role: "user", time: { created: index + 1 } },
      parts: [{ type: "text", text }],
    })),
  }
}

/** The trailing snapshot text appended by `messages.transform` ("" when none was appended). */
function appendedSnapshot(
  out: { messages: Array<{ parts: Array<{ type: string; text?: string }> }> },
  baseCount: number,
): string {
  if (out.messages.length <= baseCount) return ""
  const entry = out.messages[out.messages.length - 1]
  const part = entry.parts.find((candidate) => candidate.type === "text")
  return part?.text ?? ""
}

/** Deliver one request through the messages transform; returns the outgoing list + appended text. */
async function deliver(
  hooks: any,
  sessionID: string,
  texts: string[] = ["do the task"],
): Promise<{ out: any; appended: string }> {
  const out = requestMessages(sessionID, texts)
  await hooks["experimental.chat.messages.transform"]({}, out)
  return { out, appended: appendedSnapshot(out, texts.length) }
}

/** The system array the transform emits for one request. */
async function systemLines(hooks: any, sessionID: string): Promise<string[]> {
  const out = { system: [] as string[] }
  await hooks["experimental.chat.system.transform"]({ sessionID }, out)
  return out.system
}

/** The snapshot text the plugin ATTACHED to the user message ("" when none). */
function attachedSnapshot(
  parts: Array<{ type?: string; text?: string }>,
): string {
  const part = parts.find(
    (candidate) =>
      candidate.type === "text" &&
      typeof candidate.text === "string" &&
      candidate.text.startsWith("[aio-context]"),
  )
  return part?.text ?? ""
}

/** Deliver one user message through `chat.message`; returns the (mutated) parts + attached text.
 *  The runtime persists these parts with the message — earlier messages are never touched. */
async function attach(
  hooks: any,
  sessionID: string,
  agent: string,
  text: string,
  id = "msg_1",
): Promise<{ parts: any[]; attached: string }> {
  const ctx = message(sessionID, agent, text, id)
  await hooks["chat.message"](...Object.values(ctx))
  return { parts: ctx.output.parts as any[], attached: attachedSnapshot(ctx.output.parts as any[]) }
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
  test("every message carries its own persisted snapshot part; earlier messages are never rewritten", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    const first = await attach(hooks, "ses_a", "aio-control", "do the task", "m1")
    const firstParts = JSON.parse(JSON.stringify(first.parts))
    const second = await attach(hooks, "ses_a", "aio-control", "continue", "m2")

    expect(first.attached).toContain("CAPSULE:ses_a")
    expect(second.attached).toContain("CAPSULE:ses_a")
    expect(first.attached).toContain("[aio-context] snapshot")
    // The delivery is a well-formed PERSISTED part: text, synthetic, bound to its message.
    const part = first.parts.find((candidate: any) => candidate.synthetic === true)
    expect(part.type).toBe("text")
    expect(part.sessionID).toBe("ses_a")
    expect(part.messageID).toBe("m1")
    // The second attach never touches the first message's parts (append-only, per message).
    expect(first.parts).toEqual(firstParts)
    // The capsule request is identity-scoped — never a "latest close" read.
    const capsuleCalls = calls.filter((c) => modeOf(c.args) === "capsule")
    expect(capsuleCalls.length).toBeGreaterThan(0)
    for (const call of capsuleCalls) {
      expect(sessionOf(call.args)).toBe("ses_a")
      expect(call.args).not.toContain("--slug")
    }
  })

  test("the system prompt is byte-stable across requests while the snapshot changes", async () => {
    // The 2026-09-17 review defect: a capsule (with an observation timestamp) inserted into
    // the system prompt changed the request PREFIX and re-billed the entire context. The
    // system array must now be identical on every request, whatever the capsule says.
    let counter = 0
    const { runner } = fakeRunner((mode, args) => {
      if (mode === "bind") {
        return { schema: "session-binding/v1", status: "created", native_session_id: sessionOf(args) }
      }
      if (mode === "capsule") {
        counter += 1
        return {
          schema: "session-capsule/v1",
          capsule_status: "composed",
          capsule: { text: `CAPSULE observed-at t${counter}: budget 1/2` },
        }
      }
      return undefined
    })
    const hooks = await makePlugin(runner, { capsuleTtlMs: 0 })

    const first = await systemLines(hooks, "ses_stable")
    const before = await attach(hooks, "ses_stable", "aio-control", "task", "m1") // observation t1
    const after = await attach(hooks, "ses_stable", "aio-control", "continue", "m2") // t2
    const second = await systemLines(hooks, "ses_stable")

    expect(first).toEqual(second) // byte-stable: no timestamp, no counters, no capsule
    expect(first.join()).not.toContain("CAPSULE")
    expect(first.join()).not.toContain("observed-at")
    expect(first.join()).not.toContain("budget")
    expect(before.attached).toContain("CAPSULE observed-at t1")
    expect(after.attached).toContain("CAPSULE observed-at t2")
  })

  test("two concurrent tasks do not exchange capsules", async () => {
    const bound = new Set<string>()
    const { runner } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    const one = await attach(hooks, "ses_one", "aio-control", "task one", "m1")
    const two = await attach(hooks, "ses_two", "aio-control", "task two", "m2")

    expect(one.attached).toContain("CAPSULE:ses_one")
    expect(two.attached).toContain("CAPSULE:ses_two")
    expect(one.attached).not.toContain("ses_two")
    expect(two.attached).not.toContain("ses_one")
  })

  test("an unrelated newer close is never requested or injected", async () => {
    // The plugin passes ONLY the bound session identity to the composer; the composer's
    // predecessor resolution is by the binding's explicit slug (Python-tested). Here we
    // assert the two properties the plugin owns: no slug/latest read, verbatim delivery.
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
    const delivered = await attach(hooks, "ses_a", "aio-control", "task", "m1")

    expect(calls.some((c) => c.args.includes("--slug"))).toBe(false)
    expect(delivered.attached).toContain("predecessor: bound-task (sha abc) — no newer-close content")
  })

  test("worker sessions receive no private coordinator capsule", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const hooks = await makePlugin(runner)

    const worker = await attach(hooks, "ses_w", "build", "implement it", "m1")
    const lines = await systemLines(hooks, "ses_w")

    expect(lines).toEqual([])
    expect(worker.attached).toBe("") // no snapshot part attached
    expect(worker.parts.length).toBe(1) // the worker's own text only
    expect(calls.some((c) => modeOf(c.args) === "capsule")).toBe(false)
    expect(calls.some((c) => modeOf(c.args) === "bind")).toBe(false)
  })

  test("a restart rehydrates the binding from the durable store", async () => {
    const bound = new Set<string>()
    const { runner, calls } = fakeRunner(happyResponder(bound))
    const first = await makePlugin(runner)
    await first["chat.message"](...Object.values(message("ses_r", "aio-control", "task")))
    const before = calls.filter((c) => modeOf(c.args) === "capsule").length

    // A fresh plugin instance (a coordinator restart): no process-local map survives — the
    // next message still receives the capsule from the durable binding.
    const second = await makePlugin(runner)
    const delivered = await attach(second, "ses_r", "aio-control", "post-restart request", "m2")

    expect(delivered.attached).toContain("CAPSULE:ses_r")
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

  test("missing store differs from a missing binding, never a fabricated capsule", async () => {
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
      const lines = await systemLines(hooks, session)
      // Unknown (never-observed) sessions get the static orientation line and nothing else:
      // no fabricated capsule, no invented notice, never a crash.
      expect(lines.length).toBe(1)
      expect(lines[0]).toContain("[aio-context]")
      expect(lines[0]).not.toContain("capsule unavailable")
      const delivered = await deliver(hooks, session)
      expect(delivered.appended).toBe("")
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
        : {
            schema: "session-binding/v1",
            status: "created",
            native_session_id: "ses_big",
          },
    )
    const hooks = await makePlugin(runner, { capsuleMaxChars: 100 })
    const delivered = await attach(hooks, "ses_big", "aio-control", "task", "m1")

    // The plugin floors a tiny custom limit at MIN_CAPSULE_CHARS (600) so the protected
    // tail can never be cut; the oversized capsule is still truncated explicitly.
    expect(delivered.attached.length).toBeLessThan(900)
    expect(delivered.attached.length).toBeGreaterThan(600)
    expect(delivered.attached).toContain("[capsule truncated by the plugin:")
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

    const messages = { messages: [] as unknown[] }
    await hooks["experimental.chat.messages.transform"]({}, messages)
    expect(messages.messages).toEqual([])
    expect(calls.length).toBe(0)
  })
})

// ── The cache discipline (2026-09-17 review repair): append-only trailing snapshots ─────────

describe("aio-context plugin — append-only trailing snapshots (cache repair)", () => {
  test("ordinary turns, tool loops and refreshes keep earlier messages byte-identical", async () => {
    // The reviewer's reproduction: a capsule in the SYSTEM prompt changed the request prefix
    // and re-billed the whole conversation. The repair delivers it as a trailing message; the
    // request sequence across turns/tool loops/refreshes must stay append-only: earlier
    // messages byte-identical, only the new suffix growing.
    let capsuleText = "CAPSULE v1"
    const { runner } = fakeRunner((mode, args) => {
      if (mode === "bind") {
        return { schema: "session-binding/v1", status: "created", native_session_id: sessionOf(args) }
      }
      if (mode === "capsule") {
        return {
          schema: "session-capsule/v1",
          capsule_status: "composed",
          capsule: { text: capsuleText },
        }
      }
      return undefined
    })
    const hooks = await makePlugin(runner, { capsuleTtlMs: 0 })

    // The runtime: each user message is delivered through `chat.message` (the plugin attaches
    // its snapshot part), then PERSISTED with it; every model call rebuilds the list from
    // storage. Requests are handed FRESH, FROZEN copies — a touch of an earlier message throws.
    type Entry = {
      info: { id: string; sessionID: string; role: string; time: { created: number } }
      parts: Array<Record<string, unknown>>
    }
    const storage: Entry[] = []
    const deliverUser = async (id: string, text: string) => {
      const ctx = message("ses_seq", "aio-control", text, id)
      await hooks["chat.message"](...Object.values(ctx))
      storage.push({
        info: { id, sessionID: "ses_seq", role: "user", time: { created: storage.length + 1 } },
        parts: (ctx.output.parts as Array<Record<string, unknown>>).map((part) => ({ ...part })),
      })
    }
    const push = (id: string, role: string, text: string) => {
      storage.push({
        info: { id, sessionID: "ses_seq", role, time: { created: storage.length + 1 } },
        parts: [{ type: "text", text }],
      })
    }
    const asRequest = () => ({
      messages: storage.map((entry) => {
        const parts = entry.parts.map((part) => Object.freeze({ ...part }))
        return Object.freeze({ info: Object.freeze({ ...entry.info }), parts: Object.freeze(parts) })
      }),
    })
    const sent: Array<{ base: number; out: { messages: Entry[] }; expected: string }> = []
    const call = async () => {
      const expected = JSON.stringify(storage) // storage at request-build time
      const out = asRequest()
      await hooks["experimental.chat.messages.transform"]({}, out)
      sent.push({ base: storage.length, out, expected })
    }

    await deliverUser("u1", "first request") //              ordinary turn 1 (attaches a part)
    await call()
    push("a1", "assistant", "tool call") //                  tool loop, same turn (tool outputs
    push("t1", "assistant", "tool result") //                ride the assistant message)
    await call()
    capsuleText = "CAPSULE v2 (new observation)" //          a capsule refresh between requests
    await call()
    await deliverUser("u2", "second request") //             ordinary turn 2 (its own new part)
    await call()

    for (let index = 0; index < sent.length; index++) {
      const { base, out, expected } = sent[index]
      // The strongest cache property: NO ephemeral inserts anywhere in the common path — the
      // outgoing request IS the stored conversation, byte for byte.
      expect(out.messages.length).toBe(base)
      expect(JSON.stringify(out.messages)).toBe(expected)
      if (index === 0) continue
      const previous = sent[index - 1]
      for (let position = 0; position < previous.base; position++) {
        expect(JSON.stringify(out.messages[position])).toBe(
          JSON.stringify(previous.out.messages[position]),
        )
      }
    }

    // The refresh attached a NEW observation to the NEW message; the first message's part is
    // exactly what it was (append-only, never a rewrite).
    expect(attachedSnapshot(storage[0].parts as any)).toContain("CAPSULE v1")
    expect(attachedSnapshot(storage[storage.length - 1].parts as any)).toContain("CAPSULE v2")
    expect(sent[sent.length - 1].out.messages[0].parts).toEqual(sent[0].out.messages[0].parts)
  })

  test("the transform appends only when the latest user message lacks a snapshot", async () => {
    // Recovery fallback: the ordinary request is left byte-pure; a request whose latest user
    // message carries NO snapshot (the post-compaction synthetic continuation, a restored
    // message, legacy history) gets exactly one trailing snapshot.
    const { runner } = fakeRunner((mode, args) => {
      if (mode === "bind") {
        return { schema: "session-binding/v1", status: "created", native_session_id: sessionOf(args) }
      }
      if (mode === "capsule") {
        return {
          schema: "session-capsule/v1",
          capsule_status: "composed",
          capsule: { text: "CAPSULE:idem" },
        }
      }
      return undefined
    })
    const hooks = await makePlugin(runner)
    const bound = await attach(hooks, "ses_idem", "aio-control", "first", "m1")

    // The ordinary request: the user message carries the persisted part — no append.
    const ordinary = {
      messages: [
        {
          info: { id: "m1", sessionID: "ses_idem", role: "user", time: { created: 1 } },
          parts: (bound.parts as Array<Record<string, unknown>>).map((part) => ({ ...part })),
        },
      ],
    }
    await hooks["experimental.chat.messages.transform"]({}, ordinary)
    expect(ordinary.messages.length).toBe(1)

    // The post-compaction continuation: no snapshot on the latest user message — ONE append.
    const continuation = {
      messages: [
        {
          info: { id: "sum", sessionID: "ses_idem", role: "assistant", time: { created: 2 }, summary: true },
          parts: [{ type: "text", text: "summary" }],
        },
        {
          info: { id: "cont", sessionID: "ses_idem", role: "user", time: { created: 3 } },
          parts: [{ type: "text", text: "Continue if you have next steps..." }],
        },
      ],
    }
    await hooks["experimental.chat.messages.transform"]({}, continuation)
    expect(continuation.messages.length).toBe(3)
    expect(appendedSnapshot(continuation, 2)).toContain("CAPSULE:idem")

    // The fallback never duplicates: the freshly appended tail IS a snapshot, so a re-run
    // over the same list leaves it alone.
    await hooks["experimental.chat.messages.transform"]({}, continuation)
    expect(continuation.messages.length).toBe(3)
  })

  test("compaction carries the capsule into the summary and the continuation gets a fresh snapshot", async () => {
    const { runner } = fakeRunner((mode, args) => {
      if (mode === "bind") {
        return { schema: "session-binding/v1", status: "created", native_session_id: sessionOf(args) }
      }
      if (mode === "capsule") {
        return {
          schema: "session-capsule/v1",
          capsule_status: "composed",
          capsule: { text: `CAPSULE:${sessionOf(args)}` },
        }
      }
      return undefined
    })
    const hooks = await makePlugin(runner)
    await hooks["chat.message"](...Object.values(message("ses_comp", "aio-control", "start")))

    // The compaction prompt must carry the durable session state (recovery).
    const compactionContext = { context: [] as string[] }
    await hooks["experimental.session.compacting"]({ sessionID: "ses_comp" }, compactionContext)
    expect(compactionContext.context.join("\n")).toContain("CAPSULE:ses_comp")

    // The synthetic continuation turn stays enabled for the coordinator…
    const continuation = { enabled: false }
    await hooks["experimental.compaction.autocontinue"]({ sessionID: "ses_comp" }, continuation)
    expect(continuation.enabled).toBe(true)

    // …while a worker keeps the runtime's own setting.
    await hooks["chat.message"](...Object.values(message("ses_comp_worker", "build", "task")))
    const workerContinuation = { enabled: false }
    await hooks["experimental.compaction.autocontinue"](
      { sessionID: "ses_comp_worker" },
      workerContinuation,
    )
    expect(workerContinuation.enabled).toBe(false)

    // The first post-compaction request (the summary + preserved tail) still receives a
    // fresh trailing snapshot — delivery is automatic; nothing to remember.
    const post = requestMessages("ses_comp", ["summary of what we did so far"])
    await hooks["experimental.chat.messages.transform"]({}, post)
    expect(appendedSnapshot(post, 1)).toContain("CAPSULE:ses_comp")
  })

  test("the delivery journal records attach refresh/continuation/unavailable and the fallback append", async () => {
    const dir = tmpDir("aio-journal-")
    try {
      const eventsPath = path.join(dir, "events.jsonl")
      let capsuleText = "CAPSULE one"
      let failing = false
      const { runner } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return { schema: "session-binding/v1", status: "created", native_session_id: sessionOf(args) }
        }
        if (mode === "capsule") {
          if (failing) return undefined
          return {
            schema: "session-capsule/v1",
            capsule_status: "composed",
            capsule: { text: capsuleText },
          }
        }
        return undefined
      })
      const hooks = await makePlugin(runner, { capsuleTtlMs: 0, eventsPath })

      await attach(hooks, "ses_j", "aio-control", "task", "m1") // 1: bind + first observation
      await attach(hooks, "ses_j", "aio-control", "next", "m2") // 2: unchanged bytes
      capsuleText = "CAPSULE two"
      await attach(hooks, "ses_j", "aio-control", "next2", "m3") // 3: a new observation
      failing = true
      await attach(hooks, "ses_j", "aio-control", "next3", "m4") // 4: the composer is down
      failing = false
      // 5: the post-compaction fallback over a message that carries no snapshot.
      const fallback = requestMessages("ses_j", ["continue if you have next steps"])
      await hooks["experimental.chat.messages.transform"]({}, fallback)

      const lines = readFileSync(eventsPath, "utf-8")
        .trim()
        .split("\n")
        .map((line) => JSON.parse(line))
      expect(lines.map((line) => line.kind)).toEqual([
        "refresh",
        "continuation",
        "refresh",
        "unavailable",
        "refresh",
      ])
      expect(lines.map((line) => line.event)).toEqual(["attach", "attach", "attach", "attach", "append"])
      expect(lines.map((line) => line.surface)).toEqual([
        "chat.message",
        "chat.message",
        "chat.message",
        "chat.message",
        "messages.transform",
      ])
      for (const line of lines) {
        expect(line.schema).toBe("aio-context-event/v1")
        expect(line.session).toBe("ses_j")
        expect(typeof line.chars).toBe("number")
      }
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })
})

// ── Unit C repairs: handoff attachment, versioned updates, explicit unavailability ──────────

import { execFileSync } from "node:child_process"
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
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
    { commandRunner: runner, capsuleTtlMs: 60_000, eventsPath: null, ...options },
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

  test("a dependency failure attaches an explicit unavailable notice for the AIO session", async () => {
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
    const delivered = await attach(hooks, "ses_fail", "aio-control", "do it", "m1")
    expect(delivered.attached).toContain("[aio-context] capsule unavailable:")
    expect(delivered.attached).toContain("store_missing")
    // The system prompt stays static in the failure case too — the notice must not leak in.
    const lines = await systemLines(hooks, "ses_fail")
    expect(lines.join()).not.toContain("store_missing")

    // A worker session gets no such notice (it is not the AIO boundary).
    const worker = await attach(hooks, "ses_worker2", "build", "task", "m2")
    const workerLines = await systemLines(hooks, "ses_worker2")
    expect(workerLines).toEqual([])
    expect(worker.attached).toBe("")
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
      const delivered = await attach(hooks, "ses_hang", "aio-control", "task", "m1")
      expect(delivered.attached).toContain("[aio-context] capsule unavailable:")
      expect(delivered.attached).toContain("timed out after 300ms")
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })
})

describe("aio-context plugin — full native path (real CLI, temporary knowledge store)", () => {
  test("a selected finding and predecessor reach the delivered snapshot text", async () => {
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
      const integration = message("ses_integration", "aio-control", "Execute Unit C repairs.")
      await hooks["chat.message"](...Object.values(integration))
      const injected = attachedSnapshot(integration.output.parts as any[])

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
      const failedCtx = message("ses_r", "aio-control", "continue")
      await hooks["chat.message"](...Object.values(failedCtx))
      const failed = attachedSnapshot(failedCtx.output.parts as any[])
      expect(failed).toContain("CAPSULE")
      expect(failed).toContain("context update failed")
      expect(failed).toContain("context version 1 remains active")

      // The NEXT message's attached snapshot must warn TOO (the notice rides every delivery
      // until a reconciliation succeeds).
      const cachedCtx = message("ses_r", "aio-control", "continue again")
      await hooks["chat.message"](...Object.values(cachedCtx))
      const cached = attachedSnapshot(cachedCtx.output.parts as any[])
      expect(cached).toContain("CAPSULE")
      expect(cached).toContain("context version 1 remains active")

      // Reconciliation: the same update now succeeds — the notice clears.
      updateShouldFail = false
      const recoveredCtx = message("ses_r", "aio-control", "continue once more")
      await hooks["chat.message"](...Object.values(recoveredCtx))
      const recovered = attachedSnapshot(recoveredCtx.output.parts as any[])
      expect(recovered).toContain("CAPSULE")
      expect(recovered).not.toContain("context update failed")
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
        const ctx = message(session, "aio-control", "start")
        await hooks["chat.message"](...Object.values(ctx))
        const bind = calls.filter((c) => modeOf(c.args) === "bind").find((c) => sessionOf(c.args) === session)!
        expect(bind.args).not.toContain("--acceptance")
        expect(bind.args).not.toContain("--predecessor-slug")
        const delivered = attachedSnapshot(ctx.output.parts as any[])
        expect(delivered).toContain("an initial handoff must name the native session id")
      }
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("a recording-advanced durable version is refreshed before a task-context update", async () => {
    // Round-10 review: submission recording advances the durable version independently of
    // the plugin's cache. The update must go out against the FRESH durable version — the
    // reviewer reproduction (cache 1, store 2) failed every attempt against the stale one.
    const project = tmpDir("aio-stale-")
    const storeVersion = { value: 2 }
    try {
      writeTaskContext(project, {
        native_session_id: "ses_rec", task: "t", work_unit: "v1", context_version: 1,
      })
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return {
            schema: "session-binding/v1", status: "created",
            binding: {
              native_session_id: sessionOf(args), context_version: 1,
              task_identity: "t", project: "",
            },
          }
        }
        if (mode === "binding") {
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args), context_version: storeVersion.value,
              task_identity: "t", project: "",
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          return {
            schema: "session-binding/v1", status: "updated",
            binding: {
              native_session_id: sessionOf(args), context_version: storeVersion.value + 1,
              task_identity: "t", project: "",
            },
          }
        }
        return undefined
      })
      const hooks = await makePluginAt(runner, project)
      await hooks["chat.message"](...Object.values(message("ses_rec", "aio-control", "start")))

      // The newer file arrives while the plugin's cache still says 1.
      writeTaskContext(project, {
        native_session_id: "ses_rec", task: "t", work_unit: "v2 work", context_version: 3,
      })
      await hooks["chat.message"](...Object.values(message("ses_rec", "aio-control", "continue")))

      const update = calls.find((c) => modeOf(c.args) === "update-context")
      expect(update).toBeDefined()
      // The update goes out against the DURABLE version (2), not the stale cache (1).
      expect(flagOf(update!.args, "--expected-version")).toBe("2")
      expect(flagOf(update!.args, "--work-unit")).toBe("v2 work")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })


  test("a recording-advanced version never silently drops a requested change", async () => {
    // Round-11 review: the durable version advanced (a submission recording; work_unit still
    // v1) while the attachment requests a work-unit change at the SAME declared version.
    // The content decides: the update MUST go out — version equality is not proof of content.
    const project = tmpDir("aio-sameness-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_drop", task: "t", work_unit: "v1", context_version: 1,
      })
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return {
            schema: "session-binding/v1", status: "created",
            binding: {
              native_session_id: sessionOf(args), context_version: 1,
              task_identity: "t", project: "", work_unit: "v1",
            },
          }
        }
        if (mode === "binding") {
          // The recording advanced the version; the work unit is unchanged.
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args), context_version: 2,
              task_identity: "t", project: "", work_unit: "v1",
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          return {
            schema: "session-binding/v1", status: "updated",
            binding: {
              native_session_id: sessionOf(args), context_version: 3,
              task_identity: "t", project: "", work_unit: "v2 work",
            },
          }
        }
        return undefined
      })
      const hooks = await makePluginAt(runner, project)
      await hooks["chat.message"](...Object.values(message("ses_drop", "aio-control", "start")))

      // The attachment declares version 2 — EQUAL to the durable version — and requests v2.
      writeTaskContext(project, {
        native_session_id: "ses_drop", task: "t", work_unit: "v2 work", context_version: 2,
      })
      await hooks["chat.message"](...Object.values(message("ses_drop", "aio-control", "continue")))

      const update = calls.find((c) => modeOf(c.args) === "update-context")
      expect(update).toBeDefined() // the silent drop must not happen
      expect(flagOf(update!.args, "--work-unit")).toBe("v2 work")
      expect(flagOf(update!.args, "--expected-version")).toBe("2") // the FRESH durable version
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("a stale attachment never overwrites an externally changed project", async () => {
    // Round-11 review: the durable project changed externally; the attachment (validated
    // against the plugin's CACHE) claims the older project. The refresh re-validates against
    // the DURABLE identity — refuse and surface, never overwrite the newer project.
    const project = tmpDir("aio-extproject-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_ext", task: "t", work_unit: "v1", context_version: 1,
      })
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return {
            schema: "session-binding/v1", status: "created",
            binding: {
              native_session_id: sessionOf(args), context_version: 1,
              task_identity: "t", project: "", work_unit: "v1",
            },
          }
        }
        if (mode === "binding") {
          // The project changed EXTERNALLY since the plugin's last read.
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args), context_version: 2,
              task_identity: "t", project: "P2", work_unit: "v1",
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          return {
            schema: "session-binding/v1", status: "updated",
            binding: { native_session_id: sessionOf(args), context_version: 3, task_identity: "t", project: "P1" },
          }
        }
        return undefined
      })
      const hooks = await makePluginAt(runner, project)
      await hooks["chat.message"](...Object.values(message("ses_ext", "aio-control", "start")))

      // The stale attachment (cached project was empty → it applies at the caller) names P1.
      writeTaskContext(project, {
        native_session_id: "ses_ext", task: "t", project: "P1", work_unit: "v2 work", context_version: 2,
      })
      const staleCtx = message("ses_ext", "aio-control", "continue")
      await hooks["chat.message"](...Object.values(staleCtx))

      // NO update call: the durable project P2 must never be overwritten by the stale P1.
      expect(calls.some((c) => modeOf(c.args) === "update-context")).toBe(false)
      const rendered = attachedSnapshot(staleCtx.output.parts as any[])
      expect(rendered).toContain("does not match the binding's project")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })


  // ── Attachment freshness (round-12): an unchanged attachment never overwrites progress ──

  function freshnessResponder(durable: Record<string, unknown>, binds: { n: number }) {
    return (mode: string, args: string[]) => {
      if (mode === "bind") {
        binds.n += 1
        const created = binds.n === 1
        return {
          schema: "session-binding/v1", status: created ? "created" : "existing",
          binding: {
            native_session_id: sessionOf(args),
            context_version: created ? 1 : 2,
            task_identity: "t", project: "",
            work_unit: created ? "w1" : durable.work_unit,
            next_action: created ? "submit workflow" : durable.next_action,
          },
        }
      }
      if (mode === "binding") {
        return {
          schema: "session-binding/v1", status: "found",
          binding: {
            native_session_id: sessionOf(args), context_version: 2,
            task_identity: "t", project: "", ...durable,
          },
        }
      }
      if (mode === "capsule") {
        return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
      }
      if (mode === "update-context") {
        return {
          schema: "session-binding/v1", status: "updated",
          binding: {
            native_session_id: sessionOf(args), context_version: 3,
            task_identity: "t", project: "",
          },
        }
      }
      return undefined
    }
  }

  for (const [caseName, durable] of [
    ["a submission recording", { work_unit: "w1", next_action: "[auto] submitted job abc123 — observe it" }],
    ["a newer work-unit update", { work_unit: "w2-direct", next_action: "submit workflow" }],
  ] as [string, Record<string, unknown>][]) {
    test(`an unchanged attachment after ${caseName} never overwrites it`, async () => {
      const project = tmpDir("aio-fresh-")
      try {
        writeTaskContext(project, {
          native_session_id: "ses_fresh", task: "t", work_unit: "w1",
          next_action: "submit workflow", context_version: 1,
        })
        const { runner, calls } = fakeRunner(freshnessResponder(durable, { n: 0 }))
        const hooks = await makePluginAt(runner, project)
        await hooks["chat.message"](...Object.values(message("ses_fresh", "aio-control", "start")))
        calls.length = 0
        // "continue" with the UNCHANGED attachment: the durable's progress stands.
        const freshCtx = message("ses_fresh", "aio-control", "continue")
        await hooks["chat.message"](...Object.values(freshCtx))
        expect(calls.some((c) => modeOf(c.args) === "update-context")).toBe(false)
        const rendered = attachedSnapshot(freshCtx.output.parts as any[])
        expect(rendered).toContain("[aio-context] snapshot")
        expect(rendered).not.toContain("context update failed")
      } finally {
        rmSync(project, { recursive: true, force: true })
      }
    })

    test(`an unchanged attachment after ${caseName} never overwrites it (plugin restart)`, async () => {
      const project = tmpDir("aio-fresh-restart-")
      try {
        writeTaskContext(project, {
          native_session_id: "ses_fresh", task: "t", work_unit: "w1",
          next_action: "submit workflow", context_version: 1,
        })
        const { runner, calls } = fakeRunner(freshnessResponder(durable, { n: 0 }))
        const first = await makePluginAt(runner, project)
        await first["chat.message"](...Object.values(message("ses_fresh", "aio-control", "start")))
        // RESTART: a fresh plugin instance over the same project — the applied marker is on
        // disk, so freshness survives the process boundary.
        const second = await makePluginAt(runner, project)
        await second["chat.message"](...Object.values(message("ses_fresh", "aio-control", "resume")))
        calls.length = 0
        await second["chat.message"](...Object.values(message("ses_fresh", "aio-control", "continue")))
        expect(calls.some((c) => modeOf(c.args) === "update-context")).toBe(false)
      } finally {
        rmSync(project, { recursive: true, force: true })
      }
    })
  }

  test("a stale attachment without a prior application surfaces the conflict", async () => {
    // Unknown freshness (marker absent, e.g. cleared): an attachment at/behind the durable
    // that differs is NOT replayed — the conflict is surfaced instead of silently dropping
    // or overwriting.
    const project = tmpDir("aio-conflict-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_conf", task: "t", work_unit: "w1", context_version: 1,
      })
      const binds = { n: 0 }
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          binds.n += 1
          return {
            schema: "session-binding/v1", status: binds.n === 1 ? "created" : "existing",
            binding: {
              native_session_id: sessionOf(args), context_version: 1,
              task_identity: "t", project: "", work_unit: "w1",
            },
          }
        }
        if (mode === "binding") {
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args), context_version: 2,
              task_identity: "t", project: "", work_unit: "w2-direct",
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          return {
            schema: "session-binding/v1", status: "updated",
            binding: {
              native_session_id: sessionOf(args), context_version: 3,
              task_identity: "t", project: "",
            },
          }
        }
        return undefined
      })
      const first = await makePluginAt(runner, project)
      await first["chat.message"](...Object.values(message("ses_conf", "aio-control", "start")))
      // The applied marker disappears (fresh state, unknown freshness).
      rmSync(path.join(project, ".opencode", "aio-context-state.json"), { force: true })
      const second = await makePluginAt(runner, project)
      await second["chat.message"](...Object.values(message("ses_conf", "aio-control", "resume")))
      calls.length = 0
      const confCtx = message("ses_conf", "aio-control", "continue")
      await second["chat.message"](...Object.values(confCtx))
      expect(calls.some((c) => modeOf(c.args) === "update-context")).toBe(false)
      const rendered = attachedSnapshot(confCtx.output.parts as any[])
      expect(rendered).toContain("not replaying stale fields")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })


  test("a concurrent task change is surfaced, never overwritten by the retry", async () => {
    // Round-13 review: the first write conflicts with a concurrent ACCEPTANCE change; the
    // retry must NOT restore the old acceptance. The authorization id/epoch distinguishes a
    // task change from progress — the conflict stays visible until the attachment is refreshed.
    const project = tmpDir("aio-conc-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_conc", task: "t", work_unit: "w1",
        acceptance: "old criteria", acceptance_source: "raw", context_version: 1,
      })
      const reads = { n: 0 }
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return {
            schema: "session-binding/v1", status: "created",
            binding: {
              native_session_id: sessionOf(args), context_version: 1,
              task_identity: "t", project: "", work_unit: "w1",
              authorization_id: "auth-1", authorization_version: 1,
            },
          }
        }
        if (mode === "binding") {
          reads.n += 1
          const concurrentTaskChange = reads.n >= 2
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args),
              context_version: concurrentTaskChange ? 3 : 2,
              task_identity: "t", project: "", work_unit: "w1",
              acceptance: {
                text: concurrentTaskChange ? "new criteria" : "old criteria",
                source: "raw",
              },
              authorization_id: concurrentTaskChange ? "auth-2" : "auth-1",
              authorization_version: concurrentTaskChange ? 2 : 1,
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        return undefined // update-context: the concurrent task change wins the race
      })
      const hooks = await makePluginAt(runner, project)
      await hooks["chat.message"](...Object.values(message("ses_conc", "aio-control", "start")))
      // A CHANGED attachment (work_unit w2) so the apply path — not the marker no-op — runs.
      writeTaskContext(project, {
        native_session_id: "ses_conc", task: "t", work_unit: "w2",
        acceptance: "old criteria", acceptance_source: "raw", context_version: 2,
      })
      calls.length = 0
      const concCtx = message("ses_conc", "aio-control", "continue")
      await hooks["chat.message"](...Object.values(concCtx))
      // attempt 0 reads auth-1 → conflict; attempt 1 reads auth-2 → SURFACE, no second write.
      expect(calls.filter((c) => modeOf(c.args) === "update-context").length).toBe(1)
      const rendered = attachedSnapshot(concCtx.output.parts as any[])
      expect(rendered).toContain("changed concurrently")
      // The conflict stays VISIBLE and is not retried on the next message either.
      calls.length = 0
      const againCtx = message("ses_conc", "aio-control", "continue")
      await hooks["chat.message"](...Object.values(againCtx))
      expect(calls.filter((c) => modeOf(c.args) === "update-context").length).toBe(0)
      const again = attachedSnapshot(againCtx.output.parts as any[])
      expect(again).toContain("changed concurrently")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("a progress-only conflict is retried against the fresh version", async () => {
    const project = tmpDir("aio-prog-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_prog", task: "t", work_unit: "w1", context_version: 1,
      })
      const reads = { n: 0 }
      const writes = { n: 0 }
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          return {
            schema: "session-binding/v1", status: "created",
            binding: {
              native_session_id: sessionOf(args), context_version: 1,
              task_identity: "t", project: "", work_unit: "w1",
              authorization_id: "auth-1", authorization_version: 1,
            },
          }
        }
        if (mode === "binding") {
          reads.n += 1
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args),
              context_version: reads.n >= 2 ? 3 : 2,
              task_identity: "t", project: "", work_unit: "w1",
              authorization_id: "auth-1", authorization_version: 1, // PROGRESS-ONLY bump
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          writes.n += 1
          if (writes.n === 1) return undefined // the recording wins the first race
          return {
            schema: "session-binding/v1", status: "updated",
            binding: {
              native_session_id: sessionOf(args), context_version: 4,
              task_identity: "t", project: "",
            },
          }
        }
        return undefined
      })
      const hooks = await makePluginAt(runner, project)
      await hooks["chat.message"](...Object.values(message("ses_prog", "aio-control", "start")))
      writeTaskContext(project, {
        native_session_id: "ses_prog", task: "t", work_unit: "w2", context_version: 2,
      })
      calls.length = 0
      const progCtx = message("ses_prog", "aio-control", "continue")
      await hooks["chat.message"](...Object.values(progCtx))
      const updateCalls = calls.filter((c) => modeOf(c.args) === "update-context")
      expect(updateCalls.length).toBe(2) // attempted, conflicted, retried
      expect(flagOf(updateCalls[1].args, "--expected-version")).toBe("3") // the fresh version
      const rendered = attachedSnapshot(progCtx.output.parts as any[])
      expect(rendered).toContain("[aio-context] snapshot")
      expect(rendered).not.toContain("context update failed")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

  test("an unversioned attachment with unknown freshness is surfaced, never replayed", async () => {
    // Round-13 review: an EXISTING binding + NO applied marker + NO declared version =
    // UNKNOWN freshness (the upgrade case) — preserve durable state, surface the conflict.
    const project = tmpDir("aio-noversion-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_nv", task: "t", work_unit: "w1", // no context_version
      })
      const binds = { n: 0 }
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          binds.n += 1
          const created = binds.n === 1
          return {
            schema: "session-binding/v1", status: created ? "created" : "existing",
            binding: {
              native_session_id: sessionOf(args), context_version: created ? 1 : 2,
              task_identity: "t", project: "",
              work_unit: created ? "w1" : "w2-direct",
              next_action: created ? "" : "[auto] submitted job abc123",
            },
          }
        }
        if (mode === "binding") {
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args), context_version: 2,
              task_identity: "t", project: "", work_unit: "w2-direct",
              next_action: "[auto] submitted job abc123",
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          return {
            schema: "session-binding/v1", status: "updated",
            binding: {
              native_session_id: sessionOf(args), context_version: 3,
              task_identity: "t", project: "",
            },
          }
        }
        return undefined
      })
      const first = await makePluginAt(runner, project)
      await first["chat.message"](...Object.values(message("ses_nv", "aio-control", "start")))
      // The upgrade shape: the applied marker is absent.
      rmSync(path.join(project, ".opencode", "aio-context-state.json"), { force: true })
      const second = await makePluginAt(runner, project)
      await second["chat.message"](...Object.values(message("ses_nv", "aio-control", "resume")))
      calls.length = 0
      const nvCtx = message("ses_nv", "aio-control", "continue")
      await second["chat.message"](...Object.values(nvCtx))
      expect(calls.some((c) => modeOf(c.args) === "update-context")).toBe(false)
      const rendered = attachedSnapshot(nvCtx.output.parts as any[])
      expect(rendered).toContain("not replaying stale fields")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })


  test("an unresolved conflict survives a plugin restart", async () => {
    // Round-14 review: conflict state persists like applied state — after a restart, the
    // stale attachment stays REJECTED until the file itself is refreshed.
    const project = tmpDir("aio-conc-restart-")
    try {
      writeTaskContext(project, {
        native_session_id: "ses_cr", task: "t", work_unit: "w1",
        acceptance: "old criteria", acceptance_source: "raw", context_version: 1,
      })
      const binds = { n: 0 }
      const reads = { n: 0 }
      const writes = { n: 0 }
      const { runner, calls } = fakeRunner((mode, args) => {
        if (mode === "bind") {
          binds.n += 1
          const created = binds.n === 1
          return {
            schema: "session-binding/v1", status: created ? "created" : "existing",
            binding: {
              native_session_id: sessionOf(args), context_version: created ? 1 : 3,
              task_identity: "t", project: "", work_unit: "w1",
              authorization_id: created ? "auth-1" : "auth-2",
              authorization_version: created ? 1 : 2,
            },
          }
        }
        if (mode === "binding") {
          reads.n += 1
          const concurrentTaskChange = reads.n >= 2
          return {
            schema: "session-binding/v1", status: "found",
            binding: {
              native_session_id: sessionOf(args),
              context_version: concurrentTaskChange ? 3 : 2,
              task_identity: "t", project: "", work_unit: "w1",
              acceptance: {
                text: concurrentTaskChange ? "new criteria" : "old criteria",
                source: "raw",
              },
              authorization_id: concurrentTaskChange ? "auth-2" : "auth-1",
              authorization_version: concurrentTaskChange ? 2 : 1,
            },
          }
        }
        if (mode === "capsule") {
          return { schema: "session-capsule/v1", capsule_status: "composed", capsule: { text: "CAPSULE" } }
        }
        if (mode === "update-context") {
          writes.n += 1
          return undefined // never accepted in this scenario
        }
        return undefined
      })
      const first = await makePluginAt(runner, project)
      await first["chat.message"](...Object.values(message("ses_cr", "aio-control", "start")))
      // The conflict: a CHANGED attachment applied against a concurrent acceptance change.
      writeTaskContext(project, {
        native_session_id: "ses_cr", task: "t", work_unit: "w2",
        acceptance: "old criteria", acceptance_source: "raw", context_version: 2,
      })
      await first["chat.message"](...Object.values(message("ses_cr", "aio-control", "continue")))
      expect(writes.n).toBe(1) // attempt 0 only; attempt 1 surfaced instead of retrying

      // RESTART the plugin (fresh instance over the same project).
      const second = await makePluginAt(runner, project)
      // The reviewer's sequence: "resume", then "continue".
      await second["chat.message"](...Object.values(message("ses_cr", "aio-control", "resume")))
      const before = writes.n
      const crCtx = message("ses_cr", "aio-control", "continue")
      await second["chat.message"](...Object.values(crCtx))
      expect(writes.n).toBe(before) // the stale attachment stays rejected
      const rendered = attachedSnapshot(crCtx.output.parts as any[])
      expect(rendered).toContain("changed concurrently")
    } finally {
      rmSync(project, { recursive: true, force: true })
    }
  })

})
