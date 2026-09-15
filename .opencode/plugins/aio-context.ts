/**
 * AIO context plugin — native session identity binding + capsule injection (Unit C).
 *
 * Hand-authored, outside the generated-surface set (see `.opencode/plugins/README.md`).
 * Auto-loaded from `.opencode/plugins/` (opencode ≥1.18 supports both `plugin/` and
 * `plugins/` as loader locations).
 *
 * Per native hook (verified against the deployed opencode 1.18.15 `@opencode-ai/plugin`
 * interfaces):
 *
 *  - `chat.message` — observe the native `sessionID` and the RESOLVED `output.message.agent`
 *    (`input.agent` may be absent). A coordinator session's first substantive message binds
 *    the session durably (original request + hash + initiating message id) through
 *    `session_open.py --bind`. Later messages — continues, compacted summaries — NEVER
 *    rebind; a restart re-binds through the durable read (status `existing`). Worker sessions
 *    are observed honestly and never bound.
 *
 *  - `experimental.chat.system.transform` — receives an optional `sessionID` (no agent).
 *    With identity and a durable binding, compose the capsule (`session_open.py --capsule`)
 *    and append it to `output.system`. Auxiliary calls without identity are skipped, and a
 *    known worker session is skipped without a store read. The hook runs on every request, so
 *    a post-compaction request re-appends the capsule from the durable binding — a bounded
 *    TTL cache only avoids re-spawning the composer.
 *
 *  - `tool.execute.before` — the early consequential-submit check: an AIO session with no
 *    binding refuses `run_workflow` with an explicit message. Convenience + early warning
 *    ONLY; backend enforcement is Unit D behavior and is NOT implemented yet.
 *
 * Identity is per call (`input.sessionID` / `output.message.agent` / `ctx`): the plugin never
 * sets a process-global session id in the multi-session server, and workers, special profiles,
 * and auxiliary calls get no private coordinator capsule.
 *
 * Test seam: `options.commandRunner` (tests inject a fake; production uses node:child_process).
 */
import type { Plugin } from "@opencode-ai/plugin"

/** The coordinator agent profile (the project's `default_agent`, see opencode.json). */
const AIO_AGENT = "aio-control"

/** Tools whose invocation is a consequential submit for the AIO boundary (early check only). */
const CONSEQUENTIAL_TOOLS = ["run_workflow"]

/** Default capsule cache TTL: the capsule is rebuilt from durable state when it expires. */
const CAPSULE_TTL_MS = 30_000

/** Default capsule size bound (the composer's bound is authoritative; this is the last resort). */
const CAPSULE_MAX_CHARS = 16_000

type CommandResult = { code: number; stdout: string; stderr: string }
type CommandRunner = (
  cmd: string[],
  stdin?: string,
  env?: Record<string, string>,
) => Promise<CommandResult>

type AioContextOptions = {
  python?: string
  sessionOpen?: string
  artifactDir?: string
  controlDb?: string
  aioAgent?: string
  capsuleTtlMs?: number
  capsuleMaxChars?: number
  commandRunner?: CommandRunner
}

/** The production runner: one child process, bounded, never inherited stdio. */
async function defaultCommandRunner(
  cmd: string[],
  stdin?: string,
  env?: Record<string, string>,
): Promise<CommandResult> {
  const { spawn } = await import("node:child_process")
  return await new Promise<CommandResult>((resolve) => {
    const child = spawn(cmd[0], cmd.slice(1), {
      stdio: ["pipe", "pipe", "pipe"],
      env: env ? { ...process.env, ...env } : process.env,
    })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => (stdout += String(chunk)))
    child.stderr.on("data", (chunk) => (stderr += String(chunk)))
    child.on("error", (err) => resolve({ code: -1, stdout, stderr: String(err) }))
    child.on("close", (code) => resolve({ code: code ?? -1, stdout, stderr }))
    if (stdin !== undefined) child.stdin.write(stdin)
    child.stdin.end()
  })
}

export const AioContextPlugin: Plugin = async (ctx, options) => {
  const opts = (options ?? {}) as AioContextOptions
  const python = opts.python ?? "python3"
  const sessionOpen = opts.sessionOpen ?? `${ctx.worktree ?? ctx.directory}/scripts/session_open.py`
  const aioAgent = opts.aioAgent ?? AIO_AGENT
  const ttlMs = opts.capsuleTtlMs ?? CAPSULE_TTL_MS
  const maxChars = opts.capsuleMaxChars ?? CAPSULE_MAX_CHARS
  const run: CommandRunner = opts.commandRunner ?? defaultCommandRunner

  /** Per-session resolved agent, as observed at chat.message (never a process-global id). */
  const agents = new Map<string, string>()
  /** Sessions whose durable binding this process has ensured (a cache, never the source). */
  const bound = new Set<string>()
  /** Per-session composed capsule (or a negative result) with a TTL. */
  const capsules = new Map<string, { text: string | null; at: number }>()

  function baseArgs(): string[] {
    const args = [python, sessionOpen]
    if (opts.artifactDir) args.push("--artifact-dir", opts.artifactDir)
    return args
  }

  async function sessionOpenCall(
    args: string[],
    stdin?: string,
  ): Promise<Record<string, unknown> | null> {
    const env = opts.controlDb ? { FINOPS_CONTROL_DB: opts.controlDb } : undefined
    let result: CommandResult
    try {
      result = await run([...baseArgs(), ...args], stdin, env)
    } catch {
      return null // a failed dependency is "no capsule", never a crashed session
    }
    if (result.code !== 0 || !result.stdout.trim()) return null
    try {
      const parsed = JSON.parse(result.stdout)
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null
    } catch {
      return null
    }
  }

  async function readBinding(sessionID: string): Promise<Record<string, unknown> | null> {
    const report = await sessionOpenCall(["--binding", "--native-session-id", sessionID, "--json"])
    if (!report || report.status !== "found" || !report.binding) return null
    return report.binding as Record<string, unknown>
  }

  async function bindSession(
    sessionID: string,
    agent: string,
    messageID: string,
    request: string,
  ): Promise<boolean> {
    const report = await sessionOpenCall(
      [
        "--bind",
        "--native-session-id", sessionID,
        "--agent", agent,
        "--message-id", messageID,
        "--request-file", "-",
        "--json",
      ],
      request,
    )
    const status = report?.status
    // `existing` is the durable read answering a restart — the original request stands.
    return status === "created" || status === "existing"
  }

  async function composeCapsuleText(sessionID: string): Promise<string | null> {
    const report = await sessionOpenCall([
      "--capsule",
      "--native-session-id", sessionID,
      "--json",
      "--max-chars", String(maxChars),
    ])
    if (!report || report.capsule_status !== "composed") return null
    const capsule = report.capsule as { text?: unknown } | undefined
    const text = typeof capsule?.text === "string" ? capsule.text : null
    if (!text) return null
    if (text.length > maxChars) {
      return (
        text.slice(0, maxChars) +
        `\n[capsule truncated by the plugin: ${text.length - maxChars} chars omitted]`
      )
    }
    return text
  }

  return {
    "chat.message": async (input, output) => {
      const sessionID = input.sessionID
      if (!sessionID) return
      const agent = String(output?.message?.agent ?? input.agent ?? "")
      agents.set(sessionID, agent)
      // Workers and special profiles are never bound to the AIO spine.
      if (agent !== aioAgent) return
      if (bound.has(sessionID)) {
        // A later message never rebuilds the binding (continue/compacted summaries must not
        // replace the original request) — but it does invalidate the capsule cache.
        capsules.delete(sessionID)
        return
      }
      const parts = Array.isArray(output?.parts) ? output.parts : []
      const request = parts
        .filter((part) => part && (part as { type?: string }).type === "text")
        .map((part) => String((part as { text?: unknown }).text ?? ""))
        .join("\n")
        .trim()
      if (!request) return
      const messageID = String(output?.message?.id ?? input.messageID ?? "")
      if (await bindSession(sessionID, agent, messageID, request)) bound.add(sessionID)
      capsules.delete(sessionID)
    },

    "experimental.chat.system.transform": async (input, output) => {
      const sessionID = input?.sessionID
      if (!sessionID) return // auxiliary call without identity — never inject
      if (!Array.isArray(output?.system)) return
      // A session already observed as a worker gets no coordinator capsule, no store read.
      const knownAgent = agents.get(sessionID)
      if (knownAgent && knownAgent !== aioAgent) return
      const cached = capsules.get(sessionID)
      if (cached && Date.now() - cached.at < ttlMs) {
        if (cached.text) output.system.push(cached.text)
        return
      }
      const text = await composeCapsuleText(sessionID)
      capsules.set(sessionID, { text, at: Date.now() })
      if (text) output.system.push(text)
      // No capsule: an unbound/unknown session receives nothing — never another session's.
    },

    "tool.execute.before": async (input) => {
      if (!CONSEQUENTIAL_TOOLS.includes(input.tool)) return
      const sessionID = input.sessionID
      if (!sessionID) return
      // Only the COORDINATOR boundary is checked: a known worker (or an unattributed session)
      // is not the AIO, and valid non-AIO automation keeps its existing contract.
      if (agents.get(sessionID) !== aioAgent) return
      if (await readBinding(sessionID)) return
      throw new Error(
        "[aio-context] refusing a consequential submit from an unbound AIO session " +
          `(${input.tool}): no durable session binding resolved for ${sessionID}. ` +
          "This early check is convenience only — backend enforcement is Unit D behavior " +
          "and is not implemented yet.",
      )
    },
  }
}
