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
 *    `session_open.py --bind`, ATTACHING the explicitly selected handoff from
 *    `.opencode/aio-task-context.json` when present (task identity, predecessor slug, finding
 *    ids, acceptance + provenance, project, source revision, work unit, next action, blocker).
 *    Later messages never rebind; a task-context file with a HIGHER `context_version` triggers
 *    an explicit, versioned `--update-context` (the original request is never replaced).
 *    Worker sessions are observed honestly and never bound.
 *
 *  - `experimental.chat.system.transform` — receives an optional `sessionID` (no agent).
 *    With identity and a durable binding, compose the capsule (`session_open.py --capsule`)
 *    and append it to `output.system`. Auxiliary calls without identity are skipped, and a
 *    known worker session is skipped without a store read. The hook runs on every request, so
 *    a post-compaction request re-appends the capsule from the durable binding. For a known
 *    AIO session whose capsule cannot be composed, a short explicit UNAVAILABLE notice is
 *    injected instead of silence (a dependency failure must not disappear).
 *
 *  - `tool.execute.before` — the early consequential-submit check: an AIO session with no
 *    binding refuses `run_workflow` with an explicit message. Convenience + early warning
 *    ONLY; the backend enforcement is the fleet exec boundary (Unit D,
 *    scripts/fleet/spawn_wrapper.py `_validate_aio_binding`, re-run strictly by the host
 *    launch broker before the launch effect) — never a substitute for it.
 *
 * Identity is per call (`input.sessionID` / `output.message.agent` / `ctx`): the plugin never
 * sets a process-global session id in the multi-session server, and workers, special profiles,
 * and auxiliary calls get no private coordinator capsule.
 *
 * Test seams: `options.commandRunner` (tests inject a fake; production uses
 * node:child_process with a hard timeout + an output cap).
 */
import type { Plugin } from "@opencode-ai/plugin"

/** The coordinator agent profile (the project's `default_agent`, see opencode.json). */
const AIO_AGENT = "aio-control"

/** Tools whose invocation is a consequential submit for the AIO boundary (early check only). */
const CONSEQUENTIAL_TOOLS = ["run_workflow"]

/** The explicit handoff attachment: written by the controller/AIO, read by this plugin. */
const TASK_CONTEXT_FILE = ".opencode/aio-task-context.json"

/** Default capsule cache TTL: the capsule is rebuilt from durable state when it expires. */
const CAPSULE_TTL_MS = 30_000

/** Default capsule size bound (the composer's bound is authoritative; this is the last resort). */
const CAPSULE_MAX_CHARS = 16_000

/** The capsule floor (mirrors the composer's MIN_CAPSULE_CHARS): below it the protected tail
 *  cannot fit, and a slice against the raw request would cut the blocker while claiming
 *  preservation. Small custom limits are raised to the floor. */
const MIN_CAPSULE_CHARS = 600

/** Hard deadline for ONE companion command (a hung child must not hang the session). */
const COMMAND_TIMEOUT_MS = 15_000

/** Output cap for ONE companion command; a truncated JSON payload is treated as a failure. */
const MAX_OUTPUT_BYTES = 262_144

type CommandResult = {
  code: number
  stdout: string
  stderr: string
  timedOut?: boolean
}
type CommandRunner = (
  cmd: string[],
  stdin?: string,
  env?: Record<string, string>,
  timeoutMs?: number,
  maxOutputBytes?: number,
) => Promise<CommandResult>

type AioContextOptions = {
  python?: string
  sessionOpen?: string
  artifactDir?: string
  controlDb?: string
  aioAgent?: string
  capsuleTtlMs?: number
  capsuleMaxChars?: number
  commandTimeoutMs?: number
  maxOutputBytes?: number
  commandRunner?: CommandRunner
}

/** The production runner: one bounded child process, killed at the deadline, output-capped. */
async function defaultCommandRunner(
  cmd: string[],
  stdin?: string,
  env?: Record<string, string>,
  timeoutMs: number = COMMAND_TIMEOUT_MS,
  maxOutputBytes: number = MAX_OUTPUT_BYTES,
): Promise<CommandResult> {
  const { spawn } = await import("node:child_process")
  return await new Promise<CommandResult>((resolve) => {
    const child = spawn(cmd[0], cmd.slice(1), {
      stdio: ["pipe", "pipe", "pipe"],
      env: env ? { ...process.env, ...env } : process.env,
      // Own process group: a hung child's grandchildren cannot outlive the deadline.
      detached: true,
    })
    let stdout = ""
    let stderr = ""
    let timedOut = false
    let settled = false
    const finish = (result: CommandResult) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(result)
    }
    const timer = setTimeout(() => {
      timedOut = true
      try {
        process.kill(-(child.pid as number), "SIGKILL") // the whole group
      } catch {
        child.kill("SIGKILL")
      }
      // Settle at the deadline: an orphaned grandchild holding the stdio pipes must never
      // keep the promise (and therefore the session's turn) hanging.
      finish({ code: -1, stdout, stderr, timedOut: true })
    }, timeoutMs)
    child.stdout.on("data", (chunk) => {
      if (stdout.length < maxOutputBytes) stdout += String(chunk)
    })
    child.stderr.on("data", (chunk) => {
      if (stderr.length < maxOutputBytes) stderr += String(chunk)
    })
    child.on("error", (err) => {
      finish({ code: -1, stdout, stderr: String(err), timedOut })
    })
    child.on("close", (code) => {
      finish({ code: code ?? -1, stdout, stderr, timedOut })
    })
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
  const maxChars = Math.max(opts.capsuleMaxChars ?? CAPSULE_MAX_CHARS, MIN_CAPSULE_CHARS)
  const timeoutMs = opts.commandTimeoutMs ?? COMMAND_TIMEOUT_MS
  const maxOutputBytes = opts.maxOutputBytes ?? MAX_OUTPUT_BYTES
  const run: CommandRunner = opts.commandRunner ?? defaultCommandRunner

  /** Per-session resolved agent, as observed at chat.message (never a process-global id). */
  const agents = new Map<string, string>()
  /** Sessions whose durable binding this process has ensured (a cache, never the source). */
  const bound = new Set<string>()
  /** The task-context version last applied per session (for versioned updates). */
  const contextVersions = new Map<string, number>()
  /** The binding's task identity per session — the reference a handoff update must match. */
  const taskIdentities = new Map<string, string>()
  /** The binding's project identity per session — validated before any update applies. */
  const projects = new Map<string, string>()
  /** The last dependency failure per session — surfaced, never swallowed. */
  const failures = new Map<string, string>()
  /** Per-session composed capsule (or a negative result + notice) with a TTL. */
  const capsules = new Map<string, { text: string | null; notice: string | null; at: number }>()

  function baseArgs(): string[] {
    const args = [python, sessionOpen]
    if (opts.artifactDir) args.push("--artifact-dir", opts.artifactDir)
    return args
  }

  async function sessionOpenCall(
    args: string[],
    stdin?: string,
  ): Promise<{ report: Record<string, unknown> | null; error: string }> {
    const env = opts.controlDb ? { FINOPS_CONTROL_DB: opts.controlDb } : undefined
    let result: CommandResult
    try {
      result = await run([...baseArgs(), ...args], stdin, env, timeoutMs, maxOutputBytes)
    } catch (err) {
      return { report: null, error: `runner error: ${String(err)}` }
    }
    if (result.timedOut) return { report: null, error: `timed out after ${timeoutMs}ms` }
    if (result.code !== 0) {
      return {
        report: null,
        error: `exit ${result.code}: ${(result.stderr || "").trim().slice(0, 200) || "no stderr"}`,
      }
    }
    if (!result.stdout.trim()) return { report: null, error: "empty output" }
    try {
      const parsed = JSON.parse(result.stdout)
      if (parsed && typeof parsed === "object") {
        return { report: parsed as Record<string, unknown>, error: "" }
      }
      return { report: null, error: "output is not an object" }
    } catch {
      return { report: null, error: "unparseable output" }
    }
  }

  /** Read the explicit handoff attachment (absent/unreadable is simply "no context"). */
  async function readTaskContext(): Promise<Record<string, unknown> | null> {
    try {
      const { readFileSync } = await import("node:fs")
      const path = `${ctx.worktree ?? ctx.directory}/${TASK_CONTEXT_FILE}`
      const parsed = JSON.parse(readFileSync(path, "utf8"))
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null
    } catch {
      return null
    }
  }

  /** Whether an attachment applies to THIS session (reviewer repair: the shared file must
   *  not mix different sessions' tasks). Selection is by native session id, or by an
   *  explicitly validated task/project reference — never "whoever reads it next". */
  function contextAppliesTo(
    context: Record<string, unknown> | null,
    sessionID: string,
    boundTask: string | undefined,
    boundProject: string | undefined,
  ): { applies: boolean; reason: string; surface: boolean } {
    if (!context) return { applies: false, reason: "no task-context attachment", surface: false }
    const contextSession = String(context.native_session_id ?? "").trim()
    if (contextSession && contextSession !== sessionID) {
      // Another session's attachment: simply not ours. Silence, not noise.
      return { applies: false, reason: `attachment names session ${contextSession}`, surface: false }
    }
    const contextTask = String(context.task ?? "").trim()
    const contextProject = String(context.project ?? "").trim()
    if (!boundTask && !boundProject && !contextSession) {
      // Reviewer repair: an INITIAL handoff must name the native session id. A task/project
      // reference alone cannot be validated against a fresh session's identity — accepting it
      // let an unrelated fresh session inherit another session's task, predecessor and
      // acceptance. Task/project references remain valid for UPDATES, where the bound
      // identity is there to compare against.
      return {
        applies: false,
        reason: "an initial handoff must name the native session id (native_session_id)",
        surface: true,
      }
    }
    if (boundTask && contextTask && contextTask !== boundTask) {
      // A different task's attachment: also not ours (a task-scoped file for another task).
      return {
        applies: false,
        reason: `attachment task ${contextTask} does not match the bound task ${boundTask}`,
        surface: false,
      }
    }
    if (boundProject && contextProject && contextProject !== boundProject) {
      // It CLAIMS to apply (session/task matched) yet conflicts on project — surface it.
      return {
        applies: false,
        reason: `attachment project ${contextProject} does not match the bound project ${boundProject}`,
        surface: true,
      }
    }
    if (!contextSession && !contextTask && !contextProject) {
      // No way to validate: a configuration error worth surfacing, never a silent mix-in.
      return { applies: false, reason: "no session/task/project reference to validate", surface: true }
    }
    return { applies: true, reason: "", surface: false }
  }

  function rememberIdentity(sessionID: string, binding: Record<string, unknown> | undefined) {
    if (!binding) return
    const task = String(binding.task_identity ?? "").trim()
    const project = String(binding.project ?? "").trim()
    if (task) taskIdentities.set(sessionID, task)
    if (project) projects.set(sessionID, project)
  }

  // ── Attachment freshness (round-12 review) ─────────────────────────────────────────
  //
  // Whether an attachment is genuinely NEW or already APPLIED is tracked here, SEPARATELY
  // from the binding's concurrency version: a submission recording advances the durable
  // version without containing the attachment's fields, and an unchanged attachment must
  // never overwrite that subsequent progress. The marker is persisted beside the attachment
  // (survives plugin restarts); without a marker, freshness is UNKNOWN and the version rule
  // applies — an attachment at/behind the durable that differs is surfaced as a conflict,
  // never replayed.

  const STATE_FILE = ".opencode/aio-context-state.json"
  let appliedLoaded = false
  const appliedAttachments = new Map<string, string>()
  /** Session → the attachment digest whose application hit a TASK conflict (round-13):
   *  surfaced on every message until the attachment is refreshed. */
  const conflictedAttachments = new Map<string, string>()

  function statePath(): string {
    return `${ctx.worktree ?? ctx.directory}/${STATE_FILE}`
  }

  /** A stable digest of the attachment's APPLICABLE fields (never the file's version). */
  function attachmentDigest(context: Record<string, unknown> | null): string {
    if (!context) return ""
    const ids = Array.isArray(context.knowledge_ids)
      ? (context.knowledge_ids as unknown[]).map(String).join(",")
      : ""
    return [
      `task=${String(context.task ?? "").trim()}`,
      `predecessor=${String(context.predecessor_slug ?? "").trim()}`,
      `knowledge_ids=${ids}`,
      `acceptance=${String(context.acceptance ?? "").trim()}`,
      `acceptance_source=${String(context.acceptance_source ?? "").trim()}`,
      `acceptance_provenance=${String(context.acceptance_provenance ?? "").trim()}`,
      `project=${String(context.project ?? "").trim()}`,
      `source_revision=${String(context.source_revision ?? "").trim()}`,
      `work_unit=${String(context.work_unit ?? "").trim()}`,
      `next_action=${String(context.next_action ?? "").trim()}`,
      `blocker=${String(context.blocker ?? "").trim()}`,
    ].join("\u0000")
  }

  async function loadAppliedState(): Promise<void> {
    if (appliedLoaded) return
    appliedLoaded = true
    try {
      const { readFileSync } = await import("node:fs")
      const parsed = JSON.parse(readFileSync(statePath(), "utf8"))
      const applied = (parsed?.applied ?? {}) as Record<string, unknown>
      for (const [session, digest] of Object.entries(applied)) {
        const value = String(digest ?? "").trim()
        if (value) appliedAttachments.set(session, value)
      }
    } catch {
      // Absent/corrupt marker: freshness is UNKNOWN — the version fallback decides, and a
      // differing attachment that is not newer surfaces as a conflict rather than replaying.
    }
  }

  async function rememberApplied(sessionID: string, digest: string): Promise<void> {
    if (!digest) return
    appliedAttachments.set(sessionID, digest)
    try {
      const { mkdirSync, writeFileSync } = await import("node:fs")
      const path = statePath()
      mkdirSync(path.slice(0, path.lastIndexOf("/")), { recursive: true })
      writeFileSync(
        path,
        JSON.stringify({
          schema: "aio-context-state/v1",
          applied: Object.fromEntries(appliedAttachments),
        }),
      )
    } catch {
      // Best-effort: the in-memory marker still guards this process lifetime.
    }
  }

  /** The task-context flags shared by --bind and --update-context. */
  function taskContextFlags(context: Record<string, unknown> | null): string[] {
    if (!context) return []
    const flags: string[] = []
    const push = (flag: string, value: unknown) => {
      if (value !== undefined && value !== null && String(value).trim()) {
        flags.push(flag, String(value))
      }
    }
    push("--task", context.task)
    push("--predecessor-slug", context.predecessor_slug)
    for (const id of (context.knowledge_ids as unknown[]) ?? []) {
      push("--knowledge-id", id)
    }
    push("--acceptance", context.acceptance)
    push("--acceptance-source", context.acceptance_source)
    push("--acceptance-provenance", context.acceptance_provenance)
    push("--project", context.project)
    push("--source-revision", context.source_revision)
    push("--work-unit", context.work_unit)
    push("--next-action", context.next_action)
    push("--blocker", context.blocker)
    return flags
  }

  async function bindSession(
    sessionID: string,
    agent: string,
    messageID: string,
    request: string,
    context: Record<string, unknown> | null,
  ): Promise<boolean> {
    const { report, error } = await sessionOpenCall(
      [
        "--bind",
        "--native-session-id", sessionID,
        "--agent", agent,
        "--message-id", messageID,
        "--request-file", "-",
        ...taskContextFlags(context),
        "--context-version", String(context?.context_version ?? 1),
        "--json",
      ],
      request,
    )
    const status = report?.status
    if (status === "created" || status === "existing") {
      const binding = report?.binding as Record<string, unknown> | undefined
      contextVersions.set(sessionID, Number(binding?.context_version ?? 1))
      rememberIdentity(sessionID, binding)
      if (status === "created" && context) {
        // The binding was CREATED from this attachment: it IS applied. Mark it so later
        // messages never replay it over progress the durable accumulates (round-12).
        await loadAppliedState()
        await rememberApplied(sessionID, attachmentDigest(context))
      }
      failures.delete(sessionID)
      return true
    }
    failures.set(
      sessionID,
      `binding ${status ?? "failed"}: ${error || (report?.warnings as string[] | undefined)?.[0] || "no detail"}`,
    )
    return false
  }

  /** Read the CURRENT durable binding + version — the store is the truth, the cache a hint. */
  async function refreshDurableBinding(
    sessionID: string,
  ): Promise<{ version: number; binding: Record<string, unknown> | undefined }> {
    const { report } = await sessionOpenCall([
      "--binding", "--native-session-id", sessionID, "--json",
    ])
    const binding = report?.binding as Record<string, unknown> | undefined
    const version = Number(binding?.context_version ?? 0)
    if (version > 0) {
      contextVersions.set(sessionID, version)
      rememberIdentity(sessionID, binding)
    }
    return { version, binding }
  }

  /**
   * The attachment's PROVIDED fields that differ from the durable binding ([] when the
   * requested state is already durable). The file's context_version is never used as proof
   * of content: a recording advances the version WITHOUT containing the attachment's
   * requested change, and version equality otherwise silently dropped it (round-11 review).
   */
  function requestedFieldDiffs(
    context: Record<string, unknown> | null,
    durable: Record<string, unknown>,
  ): string[] {
    if (!context) return []
    const diffs: string[] = []
    const differs = (name: string, requested: unknown, current: unknown) => {
      const value = String(requested ?? "").trim()
      if (!value) return // an omitted field requests nothing
      if (value !== String(current ?? "").trim()) diffs.push(name)
    }
    differs("work_unit", context.work_unit, durable.work_unit)
    differs("next_action", context.next_action, durable.next_action)
    differs("blocker", context.blocker, durable.blocker)
    differs("source_revision", context.source_revision, durable.source_revision)
    differs("project", context.project, durable.project)
    const acceptance = (durable.acceptance as Record<string, unknown> | null | undefined) ?? null
    differs("acceptance", context.acceptance, acceptance?.text)
    differs("acceptance_source", context.acceptance_source, acceptance?.source)
    differs("acceptance_provenance", context.acceptance_provenance, acceptance?.provenance)
    const predecessor = (durable.predecessor as Record<string, unknown> | null | undefined) ?? null
    differs("predecessor", context.predecessor_slug, predecessor?.slug)
    const requestedIds = Array.isArray(context.knowledge_ids)
      ? (context.knowledge_ids as unknown[]).map(String).join(",")
      : ""
    const durableIds = Array.isArray(predecessor?.knowledge_ids)
      ? (predecessor?.knowledge_ids as unknown[]).map(String).join(",")
      : ""
    if (requestedIds && requestedIds !== durableIds) diffs.push("knowledge_ids")
    return diffs
  }

  async function updateSessionContext(
    sessionID: string,
    fallbackVersion: number,
    context: Record<string, unknown> | null,
  ): Promise<boolean> {
    // RECORDING-AWARE + CONTENT-DECIDED + FRESHNESS-TRACKED (rounds 10-12 review): the
    // durable version advances for reasons other than this attachment (submission recording,
    // external updates), so neither the version nor a content difference alone tells whether
    // the attachment is a NEW instruction. The applied-attachment marker answers that,
    // SEPARATELY from the version; then: refresh the durable binding → re-validate identity
    // against the DURABLE task/project → no-op when the requested fields are already durable
    // → apply a genuinely new instruction (fresh version, one retry) → surface the conflict
    // when an UNKNOWN-freshness attachment at/behind the durable would replay stale fields.
    await loadAppliedState()
    const digest = attachmentDigest(context)
    const declaredVersion = Number(context?.context_version ?? 0)
    if (digest && appliedAttachments.get(sessionID) === digest) {
      // UNCHANGED attachment already applied: the durable's later progress (the recording's
      // pending-job reference, a newer work unit) stands. Silent — nothing conflicts.
      failures.delete(sessionID)
      return true
    }
    if (digest && conflictedAttachments.get(sessionID) === digest) {
      // A TASK conflict stays VISIBLE until the attachment itself is refreshed (round-13):
      // the same stale content is not retried against the durable on every message.
      failures.set(
        sessionID,
        "task-context conflict: the task changed concurrently (acceptance / task definition) " +
          "— not retrying the update; refresh the attachment to re-assert intent",
      )
      return false
    }
    let previousAuthorization = ""
    for (let attempt = 0; attempt < 2; attempt++) {
      const refreshed = await refreshDurableBinding(sessionID)
      const durable = refreshed.binding ?? {}
      const expected = refreshed.version > 0 ? refreshed.version : fallbackVersion
      if (!expected) break
      // CONFLICT CLASSIFICATION (round-13 review): a conflict is retried ONLY when the
      // concurrent change was PROGRESS-ONLY. The binding's authorization id/epoch moves when
      // the task definition (acceptance / work unit / project) changes — retrying over THAT
      // would overwrite the concurrent writer's acceptance criteria. Task conflicts stay
      // visible until the attachment itself is refreshed (a new digest).
      const authId = String(durable.authorization_id ?? "").trim()
      const authEpoch = Number(durable.authorization_version ?? 0)
      const currentAuthorization =
        authId || (authEpoch > 0 ? `epoch:${authEpoch}` : "")
      if (
        attempt > 0 &&
        previousAuthorization &&
        currentAuthorization &&
        currentAuthorization !== previousAuthorization
      ) {
        if (digest) conflictedAttachments.set(sessionID, digest)
        failures.set(
          sessionID,
          "task-context conflict: the task changed concurrently (acceptance / task " +
            "definition) — not retrying the update; refresh the attachment to re-assert intent",
        )
        return false
      }
      previousAuthorization = currentAuthorization
      const durableTask = String(durable.task_identity ?? "").trim()
      const durableProject = String(durable.project ?? "").trim()
      const contextTask = String(context?.task ?? "").trim()
      const contextProject = String(context?.project ?? "").trim()
      if (durableTask && contextTask && contextTask !== durableTask) {
        failures.set(
          sessionID,
          `task-context not applied: attachment task ${contextTask} does not match the ` +
            `binding's task ${durableTask}`,
        )
        return false
      }
      if (durableProject && contextProject && contextProject !== durableProject) {
        failures.set(
          sessionID,
          `task-context not applied: attachment project ${contextProject} does not match ` +
            `the binding's project ${durableProject} — the attachment is stale`,
        )
        return false
      }
      if (requestedFieldDiffs(context, durable).length === 0) {
        await rememberApplied(sessionID, digest)
        failures.delete(sessionID) // the requested state is already durable
        return true
      }
      // The requested fields differ from the durable. With NO known prior application
      // (fresh plugin state, marker absent) an attachment at/behind the durable version — OR
      // with NO declared version at all (round-13: missing version + missing marker means
      // UNKNOWN freshness) — may be stale: surface the conflict instead of replaying stale
      // fields. A CHANGED file (a prior application exists with a different digest) is an
      // explicit new instruction and proceeds.
      const knownPriorApplication = appliedAttachments.has(sessionID)
      const genuinelyNew = declaredVersion > 0 && declaredVersion > refreshed.version
      if (!knownPriorApplication && !genuinelyNew) {
        failures.set(
          sessionID,
          `task-context conflict: the attachment (v${declaredVersion || "no version"}) is ` +
            `not newer than the binding (v${refreshed.version}) and its fields differ — ` +
            "not replaying stale fields; update the attachment to re-assert intent",
        )
        return false
      }
      const { report, error } = await sessionOpenCall([
        "--update-context",
        "--native-session-id", sessionID,
        "--expected-version", String(expected),
        ...taskContextFlags(context),
        "--json",
      ])
      if (report?.status === "updated") {
        const binding = report?.binding as Record<string, unknown> | undefined
        contextVersions.set(sessionID, Number(binding?.context_version ?? expected + 1))
        rememberIdentity(sessionID, binding)
        await rememberApplied(sessionID, digest)
        failures.delete(sessionID) // reconciled: the notice clears
        return true
      }
      if (attempt === 0) continue // re-read and retry once against the fresh version
      failures.set(sessionID, `context update failed: ${error || String(report?.status ?? "")}`)
      return false
    }
    failures.set(
      sessionID,
      "context update failed: no durable context version to apply against",
    )
    return false
  }

  async function composeCapsuleText(
    sessionID: string,
  ): Promise<{ text: string | null; notice: string | null }> {
    const { report, error } = await sessionOpenCall([
      "--capsule",
      "--native-session-id", sessionID,
      "--json",
      "--max-chars", String(maxChars),
    ])
    if (!report) return { text: null, notice: error }
    if (report.capsule_status !== "composed") {
      const detail = (report.warnings as string[] | undefined)?.[0]
      return { text: null, notice: `capsule ${report.capsule_status}${detail ? `: ${detail}` : ""}` }
    }
    const capsule = report.capsule as { text?: unknown } | undefined
    const text = typeof capsule?.text === "string" ? capsule.text : null
    if (!text) return { text: null, notice: "capsule composed but empty" }
    if (text.length > maxChars) {
      return {
        text:
          text.slice(0, maxChars) +
          `\n[capsule truncated by the plugin: ${text.length - maxChars} chars omitted]`,
        notice: null,
      }
    }
    return { text, notice: null }
  }

  return {
    "chat.message": async (input, output) => {
      const sessionID = input.sessionID
      if (!sessionID) return
      const agent = String(output?.message?.agent ?? input.agent ?? "")
      agents.set(sessionID, agent)
      // Workers and special profiles are never bound to the AIO spine.
      if (agent !== aioAgent) return
      const context = await readTaskContext()
      const applicable = contextAppliesTo(
        context, sessionID, taskIdentities.get(sessionID), projects.get(sessionID),
      )
      if (bound.has(sessionID)) {
        if (context && !applicable.applies && applicable.surface) {
          failures.set(sessionID, `task-context not applied: ${applicable.reason}`)
        }
        // A later message never rebuilds the binding; it can only apply an EXPLICIT,
        // versioned task-context update — and only when the attachment validates against
        // THIS session's task/project identity.
        const current = contextVersions.get(sessionID) ?? 0
        // The attachment's declared version is NOT the gate (round-11 review): a recording
        // advances the durable version while a newer attachment may still request changes
        // the store does not have (version equality silently dropped them). Applicability
        // and the DURABLE content decide inside updateSessionContext.
        if (applicable.applies) {
          await updateSessionContext(sessionID, current, context)
        }
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
      // The attachment is attached only if it applies to THIS session (or carries a
      // task reference on a first bind); otherwise the request alone is bound and the
      // mismatch is surfaced, never silently mixed in.
      const bindOk = await bindSession(
        sessionID, agent, messageID, request, applicable.applies ? context : null,
      )
      if (bindOk) bound.add(sessionID)
      if (bindOk && context && !applicable.applies && applicable.surface) {
        // The bind itself succeeded; the ATTACHMENT is what could not be applied — say so.
        failures.set(sessionID, `task-context not applied: ${applicable.reason}`)
      }
      capsules.delete(sessionID)
    },

    "experimental.chat.system.transform": async (input, output) => {
      const sessionID = input?.sessionID
      if (!sessionID) return // auxiliary call without identity — never inject
      if (!Array.isArray(output?.system)) return
      // A session already observed as a worker gets no coordinator capsule, no store read.
      const knownAgent = agents.get(sessionID)
      if (knownAgent && knownAgent !== aioAgent) return
      const emit = (text: string | null, notice: string | null) => {
        if (text) {
          output.system.push(text)
          // The failure notice rides BOTH the fresh and the cached paths, until a
          // reconciliation succeeds (reviewer repair: a cached request dropped the warning).
          const failure = failures.get(sessionID)
          if (failure) {
            const active = contextVersions.get(sessionID)
            output.system.push(
              `[aio-context] context update failed: ${failure} — context version ` +
                `${active ?? "unknown"} remains active`,
            )
          }
        } else if (knownAgent === aioAgent) {
          // Dependency failures must not disappear: a known AIO session gets an explicit,
          // short unavailable notice instead of an empty system prompt.
          output.system.push(
            `[aio-context] capsule unavailable: ${notice ?? "no durable binding for this session"}`,
          )
        }
      }
      const cached = capsules.get(sessionID)
      if (cached && Date.now() - cached.at < ttlMs) {
        emit(cached.text, cached.notice)
        return
      }
      const { text, notice } = await composeCapsuleText(sessionID)
      const failure = failures.get(sessionID)
      const effectiveNotice = notice || failure || null
      capsules.set(sessionID, { text, notice: effectiveNotice, at: Date.now() })
      emit(text, effectiveNotice)
    },

    "tool.execute.before": async (input) => {
      if (!CONSEQUENTIAL_TOOLS.includes(input.tool)) return
      const sessionID = input.sessionID
      if (!sessionID) return
      // Only the COORDINATOR boundary is checked: a known worker (or an unattributed session)
      // is not the AIO, and valid non-AIO automation keeps its existing contract.
      if (agents.get(sessionID) !== aioAgent) return
      const { report } = await sessionOpenCall([
        "--binding",
        "--native-session-id", sessionID,
        "--json",
      ])
      if (report?.status === "found") return
      throw new Error(
        "[aio-context] refusing a consequential submit from an unbound AIO session " +
          `(${input.tool}): no durable session binding resolved for ${sessionID}` +
          (report?.status ? ` (status ${String(report.status)})` : "") +
          ". This early check is convenience only — the fleet exec boundary (the spawn " +
          "wrapper / host launch broker) re-validates the binding before the launch effect " +
          "(the session capacity report is advisory diagnostics, never an admission gate).",
      )
    },
  }
}
