import { tool } from "@opencode-ai/plugin"

/**
 * The AIO identity flags for a durable submit.
 *
 * PURE and exported for the argv-level regression: the identity comes from the NATIVE tool
 * context (`ctx.sessionID` / `ctx.agent`) plus a durable binding read — never from a
 * model-supplied arg. The backend re-resolves the binding independently before any launch;
 * this helper only refuses early when the tool itself cannot supply a bound identity.
 */
export const AIO_AGENT = "aio-control"

export type CommandResult = { stdout: string; stderr: string; exitCode: number }
export type CommandRunner = (args: string[], cwd: string, stdin?: string) => Promise<CommandResult>

async function defaultCommandRunner(args: string[], cwd: string, stdin?: string): Promise<CommandResult> {
  const proc = Bun.spawn(args, { cwd, stdout: "pipe", stderr: "pipe", stdin: "pipe" })
  if (stdin !== undefined) proc.stdin.write(stdin)
  proc.stdin.end()
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  return { stdout, stderr, exitCode }
}

let commandRunner: CommandRunner = defaultCommandRunner

/** Test seam: drive the tool's REAL entry point with an injected shell. */
export function setCommandRunner(runner: CommandRunner | null): void {
  commandRunner = runner ?? defaultCommandRunner
}

/** Parse one ``session_open.py --binding`` stdout and gate it (malformed output refuses). */
export function toolBindingGate(
  agent: string,
  sessionID: string,
  bindingStdout: string,
): { flags: string[]; refuse: string } {
  let report: Record<string, unknown> | null = null
  try {
    const parsed = JSON.parse(String(bindingStdout ?? "").trim())
    report = parsed && typeof parsed === "object" ? parsed : null
  } catch {
    report = null
  }
  return aioSubmitFlags(sessionID, agent, report)
}

/** Whether the RESOLVED native agent is the AIO coordinator (never a model-supplied field). */
export function isAioAgent(agent: string): boolean {
  return String(agent ?? "").trim() === AIO_AGENT
}

export function aioSubmitFlags(
  nativeSessionID: string,
  agent: string,
  bindingReport: {
    status?: unknown
    knowledge_id?: unknown
    binding?: { context_version?: unknown; project?: unknown; task_identity?: unknown } | null
  } | null,
): { flags: string[]; refuse: string } {
  // The binding gate applies to the AIO actor. A worker / specialized profile keeps the
  // existing authority contract and is never asked to impersonate the coordinator
  // (reviewer finding: an unconditional check refused legitimate Build calls).
  if (!isAioAgent(agent)) {
    return { flags: [], refuse: "" }
  }
  const sessionID = String(nativeSessionID ?? "").trim()
  if (!sessionID) {
    return {
      flags: [],
      refuse:
        "no native session identity in the tool context — refusing to submit unbound " +
        "(the durable path requires a bound AIO session)",
    }
  }
  if (!bindingReport || bindingReport.status !== "found") {
    const status = bindingReport?.status ?? "unreadable"
    return {
      flags: [],
      refuse:
        `no durable AIO binding for session ${sessionID} (status ${status}) — the plugin ` +
        "binds the session on its first substantive message; refusing to submit unbound.",
    }
  }
  const bindingID = String(bindingReport.knowledge_id ?? "").trim()
  const revision = Number(bindingReport.binding?.context_version ?? 0)
  if (!bindingID || !Number.isInteger(revision) || revision < 1) {
    return {
      flags: [],
      refuse:
        `the AIO binding for session ${sessionID} carries no record id / task revision — ` +
        "refusing to submit unbound.",
    }
  }
  // The project association is NOT a tool flag (reviewer repair: the manager's parser never
  // accepted --project, and a tool-emitted flag the CLI rejects is a broken connection). The
  // backend resolves the project from the durable binding and validates it against the
  // submitted spec/worktree — the flag would be redundant and unparseable.
  const flags = [
    "--aio-session-id", sessionID,
    "--aio-agent", String(agent ?? ""),
    "--binding-id", bindingID,
    "--task-revision", String(revision),
  ]
  // The LOGICAL TASK identity scopes the retry-safe request key (reviewer finding,
  // 2026-09-16): the same inputs from a different task/session are a different logical
  // submission — never the first task's job. An explicit task identity (not the per-session
  // fallback) also survives session changes: a new session attached to the same task derives
  // the same key.
  const taskIdentity = String(bindingReport.binding?.task_identity ?? "").trim()
  if (taskIdentity) flags.push("--task-identity", taskIdentity)
  return { flags, refuse: "" }
}

export default tool({
  description:
    "Run an agent_task workflow (the execute phase of the spec/compiler DAG) against a goal inside a git worktree, committing + ledgering each phase. With orchestrator=true (the DEFAULT), the run is SUBMITTED through the durable fleet path (fleet:commands → spawn-wrapper consumer → host-side launch broker → docker compose), carrying source/spec identity (spec_sha256), continuation identity (resume/parent_run_id), and the admission settings — a submit immediately yields a durable job identity, and the same identity supports observation (fleet:jobs board, control packet) and continuation. With orchestrator=false the run executes in-process (an explicitly requested deterministic local run).",
  args: {
    spec: tool.schema.string().describe("Path to an ExperimentSpec OR a workflow-v1 YAML"),
    goal: tool.schema.string().describe("Feature/task prompt (substituted for {goal})"),
    model: tool.schema.string().describe("provider/model id"),
    workdir: tool.schema.string().optional().describe(
      "Git worktree path to run in. OMITTED on the durable path, the fleet preparation path selects/creates the workspace (deterministic name, reused across an identical retry; a continuation reuses the parent run's workdir). In-process runs still need an explicit workdir.",
    ),
    request_key: tool.schema.string().optional().describe(
      "Optional EXPLICIT request key. Omitted (the ordinary case), the fleet derives a stable key from the submission's execution-relevant inputs before sending — an identical retry after an ambiguous or lost response reconciles to the existing job automatically. Pass an explicit NEW key to force an independent run of identical inputs.",
    ),
    backend: tool.schema.enum(["opencode", "claude_cli"]).optional().describe("Default: auto"),
    thinking_effort: tool.schema.string().optional().default("high"),
    thinking_budget_tokens: tool.schema.number().optional().default(0),
    output_token_limit: tool.schema.number().optional().default(0),
    timeout_min: tool.schema.number().optional().default(30).describe("Per-phase timeout in minutes"),
    no_commit: tool.schema.boolean().optional().default(false),
    resume: tool.schema.boolean().optional().default(false),
    parent_run_id: tool.schema.string().optional().describe(
      "The control-db run id this submission CONTINUES (required when resuming a paused run; the run's own composition root verifies the lineage).",
    ),
    admission_required: tool.schema.boolean().optional().describe(
      "Arm the admission gate for the run (FINOPS_ADMISSION_REQUIRED=1 in the orchestrator container). Default: follow the AIO's own environment.",
    ),
    campaign_budget_usd: tool.schema.number().optional().describe(
      "The campaign budget ceiling the run applies to the lease registry (distinct from any daily real-cash allowance).",
    ),
    campaign_concurrency: tool.schema.number().optional().describe(
      "The campaign concurrency cap the run applies to the lease registry.",
    ),
    admission_reserve_usd: tool.schema.number().optional().describe(
      "Per-phase dollar reservation for per-token models (the armed gate denies without a stated reserve).",
    ),
    admission_hard_cap_usd: tool.schema.number().optional().describe(
      "Per-lease dollar ceiling for per-token models.",
    ),
    orchestrator: tool.schema.boolean().optional().default(true).describe(
      "Run through the durable containerized path (fleet submit) — the DEFAULT per the project rules. Pass false only for an explicitly requested deterministic local run.",
    ),
  },
  async execute(args, ctx) {
    // The AIO boundary applies to EVERY execution mode (reviewer finding: with the plugin
    // absent, orchestrator=false was an unbound escape into run_workflow.py). The gate runs
    // first; the native identity comes from the tool context. Non-AIO sessions skip it and
    // keep the existing authority contract.
    let aioFlags: string[] = []
    // The AIO session capacity report is ADVISORY (2026-09-16 policy): the gate measures it
    // so the result can carry it, and it never contributes to a refusal.
    let aioCapacity: Record<string, unknown> | null = null
    if (isAioAgent(String(ctx.agent ?? ""))) {
      const bindingRead = await commandRunner(
        ["python3", "scripts/session_open.py", "--binding",
         "--native-session-id", String(ctx.sessionID ?? ""), "--json"],
        ctx.directory,
      )
      const aio = toolBindingGate(
        String(ctx.agent ?? ""), String(ctx.sessionID ?? ""), bindingRead.stdout,
      )
      if (aio.refuse) {
        return {
          output: aio.refuse,
          metadata: {
            exit_code: 2,
            aio_session_id: String(ctx.sessionID ?? ""),
            execution_mode: args.orchestrator ? "durable" : "in-process",
          },
        }
      }
      aioFlags = aio.flags
    }

    if (!args.orchestrator) {
      if (!String(args.workdir ?? "").trim()) {
        // The workspace preparation path applies to DURABLE submits (the composition root
        // resolves the workspace before the launch); an in-process run executes directly in
        // the given worktree and still needs it explicitly.
        return {
          output:
            "in-process runs need an explicit workdir — the fleet preparation path applies " +
            "to durable submits (orchestrator=true).",
          metadata: { exit_code: 2, execution_mode: "in-process" },
        }
      }
      if (isAioAgent(String(ctx.agent ?? ""))) {
        // The AIO local exception (Unit D repair): an in-process run is permitted only for a
        // VERIFIED DETERMINISTIC workflow AND only when the same binding/scope gate the
        // durable path uses passes — checked through the REAL validator, so an agent workflow
        // refuses BEFORE any local execution. Conversation capacity is NOT part of the
        // refusal (2026-09-16 policy): the validator reports it as advisory diagnostics.
        const checkRequest = {
          spec: args.spec,
          goal: args.goal,
          model: args.model,
          workdir: args.workdir,
          actor: "aio",
          aio: {
            native_session_id: String(ctx.sessionID ?? ""),
            agent: String(ctx.agent ?? ""),
            binding_id: aioFlags[aioFlags.indexOf("--binding-id") + 1] ?? "",
            task_revision: Number(aioFlags[aioFlags.indexOf("--task-revision") + 1] ?? 0),
          },
        }
        const validation = await commandRunner(
          ["python3", "scripts/fleet/spawn_wrapper.py", "validate-submit",
           "--require-deterministic"],
          ctx.directory,
          JSON.stringify(checkRequest),
        )
        let verdict: {
          ok?: boolean
          errors?: string[]
          aio_capacity?: Record<string, unknown>
        } | null = null
        try {
          const parsed = JSON.parse(validation.stdout.trim())
          verdict = parsed && typeof parsed === "object" ? parsed : null
        } catch {
          verdict = null
        }
        aioCapacity = verdict?.aio_capacity ?? null
        if (!verdict || verdict.ok !== true) {
          return {
            output:
              "AIO in-process run refused: " +
              ((verdict?.errors ?? []).join("; ") ||
                `the deterministic/binding validator is unavailable (exit ${validation.exitCode})`),
            metadata: {
              exit_code: 2,
              execution_mode: "in-process",
              aio_capacity: aioCapacity,
            },
          }
        }
      }
      // The explicitly requested in-process mode (a lab execution, a deterministic replay).
      const flags: string[] = [
        "--spec", args.spec,
        "--goal", args.goal,
        "--model", args.model,
        "--workdir", args.workdir,
        "--thinking-effort", args.thinking_effort,
        "--thinking-budget-tokens", String(args.thinking_budget_tokens),
        "--output-token-limit", String(args.output_token_limit),
        "--timeout", String(args.timeout_min * 60),
      ]
      if (args.backend) flags.push("--backend", args.backend)
      if (args.no_commit) flags.push("--no-commit")
      if (args.resume) flags.push("--resume")
      const result = await commandRunner(["python3", "scripts/run_workflow.py", ...flags], ctx.directory)
      const output = result.stdout.trim()
      const err = result.stderr.trim()
      if (result.exitCode !== 0) {
        return { output: output || err || `run_workflow failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
      }
      return {
        output: output || `Workflow completed for goal "${args.goal}"`,
        metadata: { spec: args.spec, model: args.model, workdir: args.workdir, resume: args.resume, aio_capacity: aioCapacity, timestamp: new Date().toISOString() },
      }
    }

    // The durable fleet submission path. The spec's bytes are hashed HERE (the AIO's own
    // checkout) so the broker can verify the declared immutable input is what the
    // orchestrator will load. Continuation identity + admission settings ride the same
    // command and survive every hop to the compose argv.
    const digest = await commandRunner(
      ["python3", "-c",
       "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())",
       args.spec],
      ctx.directory,
    )
    const specSha = digest.stdout.trim()
    if (specSha.length !== 64) {
      return { output: `spec identity unavailable for ${args.spec} (got "${specSha}") — refusing to submit without the source digest`, metadata: { exit_code: 2 } }
    }

    const admissionArmed = args.admission_required ?? (process.env.FINOPS_ADMISSION_REQUIRED === "1")
    const submitFlags: string[] = [
      "submit",
      "--spec", args.spec,
      "--goal", args.goal,
      "--model", args.model,
      "--spec-sha256", specSha,
    ]
    // An omitted workdir rides through as an omission: the fleet preparation path selects or
    // creates the workspace (Unit 2) — the caller assembles nothing.
    if (args.workdir) submitFlags.push("--workdir", args.workdir)
    submitFlags.push(...aioFlags)
    // Retry-safe by DEFAULT (Unit 2): the ordinary path retains its identity BEFORE sending —
    // the fleet derives a stable key from the submission's execution-relevant inputs, so a
    // retry after a lost response reconciles without the AIO having to remember anything. An
    // explicit key wins (that is how a caller forces an independent new run).
    if (args.request_key) submitFlags.push("--request-key", args.request_key)
    else submitFlags.push("--retry-safe")
    if (args.resume) submitFlags.push("--resume")
    if (args.parent_run_id) submitFlags.push("--parent-run-id", args.parent_run_id)
    if (admissionArmed) submitFlags.push("--admission-required")
    if (args.campaign_budget_usd !== undefined) submitFlags.push("--campaign-budget-usd", String(args.campaign_budget_usd))
    if (args.campaign_concurrency !== undefined) submitFlags.push("--campaign-concurrency", String(args.campaign_concurrency))
    // The armed gate's per-token leases DENY without a stated reserve (an unknown cost is
    // never free); these values must survive the hop exactly like the other admission settings.
    if (args.admission_reserve_usd !== undefined) submitFlags.push("--reserve-usd", String(args.admission_reserve_usd))
    if (args.admission_hard_cap_usd !== undefined) submitFlags.push("--hard-cap-usd", String(args.admission_hard_cap_usd))
    // Every accepted execution setting is FORWARDED through the durable path (Astra finding,
    // 2026-09-14): the tool's defaults are the requested behavior, and a setting that were
    // accepted but dropped would deliver "I requested one execution behavior and got another".
    // The submit contract carries each into the orchestrator argv (wrapper step 11 validates;
    // the broker composes the flags).
    if (args.backend) submitFlags.push("--backend", args.backend)
    if (args.thinking_effort) submitFlags.push("--thinking-effort", args.thinking_effort)
    if (args.thinking_budget_tokens) submitFlags.push("--thinking-budget-tokens", String(args.thinking_budget_tokens))
    if (args.output_token_limit) submitFlags.push("--output-token-limit", String(args.output_token_limit))
    if (args.timeout_min) submitFlags.push("--timeout-seconds", String(args.timeout_min * 60))
    if (args.no_commit) submitFlags.push("--no-commit")
    // The STRUCTURED result (fleet-submit/v1): the durable interface is ONE JSON document —
    // never a human log line parsed for an identity.
    submitFlags.push("--json")

    const submit = await commandRunner(
      ["python3", "scripts/fleet/fleet_manager.py", ...submitFlags], ctx.directory,
    )
    const out = submit.stdout.trim()
    const err = submit.stderr.trim()
    if (submit.exitCode !== 0) {
      return { output: out || err || `fleet submit failed (exit ${submit.exitCode})`, metadata: { exit_code: submit.exitCode } }
    }
    let result: Record<string, unknown> | null = null
    try {
      const parsed = JSON.parse(out)
      result =
        parsed && typeof parsed === "object" && (parsed as any).schema === "fleet-submit/v1"
          ? (parsed as Record<string, unknown>)
          : null
    } catch {
      result = null
    }
    if (!result) {
      return {
        output:
          "fleet submit returned no fleet-submit/v1 result — refusing to guess the job " +
          `identity from unstructured output:\n${out || err}`,
        metadata: { exit_code: 3 },
      }
    }
    const jobId = String(result.job_id ?? "")
    // A keyed retry the fleet reconciled to an EXISTING job: nothing new was queued, and the
    // same identity carries the observation (the durable job row is the truth of what ran).
    const reconciled = Boolean(result.reconciled)
    const effectiveKey = String(result.request_key ?? args.request_key ?? "")
    const prepNote = String(result.prep_note ?? "")
    // The task-state note: "" means the submission was recorded into the durable binding
    // (the continuation glue); a non-empty note is a REPORTED, non-fatal failure to record.
    const taskNote = String(result.task_note ?? "")
    const keyNote = effectiveKey
      ? ` Request key: ${effectiveKey} — reuse it verbatim if this response is ever lost.`
      : ""
    return {
      output:
        (reconciled
          ? `RECONCILED to the EXISTING job ${jobId} under the same request key — nothing new was queued. ` +
            `Observe it under the SAME identity: control packet (active_runs) or the Control Room.`
          : `Submission accepted by the durable path: job ${jobId}. The broker validates the spec digest (${specSha.slice(0, 12)}…) and admission before the compose call; a QUEUED submit is not a running run — verify the run row exists (control packet, active_runs) before treating the build as started.`) +
        (prepNote ? ` ${prepNote}.` : "") +
        (taskNote ? ` TASK STATE: ${taskNote}.` : "") +
        keyNote,
      metadata: {
        job_id: jobId,
        reconciled,
        status: String(result.status ?? ""),
        task_note: taskNote,
        request_key: args.request_key ?? "",
        effective_request_key: effectiveKey,
        retry_safe: !args.request_key,
        spec: args.spec,
        spec_sha256: specSha,
        model: args.model,
        workdir: String(result.workdir ?? args.workdir ?? ""),
        prep_note: prepNote,
        resume: args.resume,
        parent_run_id: args.parent_run_id ?? "",
        aio_session_id: String(ctx.sessionID ?? ""),
        aio_binding_id: aioFlags[aioFlags.indexOf("--binding-id") + 1] ?? "",
        admission_required: admissionArmed,
        execution: {
          backend: args.backend ?? "auto",
          thinking_effort: args.thinking_effort,
          thinking_budget_tokens: args.thinking_budget_tokens,
          output_token_limit: args.output_token_limit,
          timeout_seconds: args.timeout_min * 60,
          no_commit: args.no_commit,
        },
        timestamp: new Date().toISOString(),
      },
    }
  },
})
