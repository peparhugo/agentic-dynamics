import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Run an agent_task workflow (the execute phase of the spec/compiler DAG) against a goal inside a git worktree, committing + ledgering each phase. With orchestrator=true (the DEFAULT), the run is SUBMITTED through the durable fleet path (fleet:commands → spawn-wrapper consumer → host-side launch broker → docker compose), carrying source/spec identity (spec_sha256), continuation identity (resume/parent_run_id), and the admission settings — a submit immediately yields a durable job identity, and the same identity supports observation (fleet:jobs board, control packet) and continuation. With orchestrator=false the run executes in-process (an explicitly requested deterministic local run).",
  args: {
    spec: tool.schema.string().describe("Path to an ExperimentSpec OR a workflow-v1 YAML"),
    goal: tool.schema.string().describe("Feature/task prompt (substituted for {goal})"),
    model: tool.schema.string().describe("provider/model id"),
    workdir: tool.schema.string().describe("Git worktree path to run in"),
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
    orchestrator: tool.schema.boolean().optional().default(true).describe(
      "Run through the durable containerized path (fleet submit) — the DEFAULT per the project rules. Pass false only for an explicitly requested deterministic local run.",
    ),
  },
  async execute(args, ctx) {
    if (!args.orchestrator) {
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
      const result = await Bun.$`python3 scripts/run_workflow.py ${flags}`.cwd(ctx.directory).nothrow()
      const output = result.stdout.toString().trim()
      const err = result.stderr.toString().trim()
      if (result.exitCode !== 0) {
        return { output: output || err || `run_workflow failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
      }
      return {
        output: output || `Workflow completed for goal "${args.goal}"`,
        metadata: { spec: args.spec, model: args.model, workdir: args.workdir, resume: args.resume, timestamp: new Date().toISOString() },
      }
    }

    // The durable fleet submission path. The spec's bytes are hashed HERE (the AIO's own
    // checkout) so the broker can verify the declared immutable input is what the
    // orchestrator will load. Continuation identity + admission settings ride the same
    // command and survive every hop to the compose argv.
    const digest = await Bun.$`python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" ${args.spec}`
      .cwd(ctx.directory).nothrow()
    const specSha = digest.stdout.toString().trim()
    if (specSha.length !== 64) {
      return { output: `spec identity unavailable for ${args.spec} (got "${specSha}") — refusing to submit without the source digest`, metadata: { exit_code: 2 } }
    }

    const admissionArmed = args.admission_required ?? (process.env.FINOPS_ADMISSION_REQUIRED === "1")
    const submitFlags: string[] = [
      "submit",
      "--spec", args.spec,
      "--goal", args.goal,
      "--model", args.model,
      "--workdir", args.workdir,
      "--spec-sha256", specSha,
    ]
    if (args.resume) submitFlags.push("--resume")
    if (args.parent_run_id) submitFlags.push("--parent-run-id", args.parent_run_id)
    if (admissionArmed) submitFlags.push("--admission-required")
    if (args.campaign_budget_usd !== undefined) submitFlags.push("--campaign-budget-usd", String(args.campaign_budget_usd))
    if (args.campaign_concurrency !== undefined) submitFlags.push("--campaign-concurrency", String(args.campaign_concurrency))

    const submit = await Bun.$`python3 scripts/fleet/fleet_manager.py ${submitFlags}`.cwd(ctx.directory).nothrow()
    const out = submit.stdout.toString().trim()
    const err = submit.stderr.toString().trim()
    if (submit.exitCode !== 0) {
      return { output: out || err || `fleet submit failed (exit ${submit.exitCode})`, metadata: { exit_code: submit.exitCode } }
    }
    const jobMatch = out.match(/fleet:jobs\[([0-9a-f]+)\]/)
    return {
      output:
        `${out}\n` +
        `Submission accepted by the durable path. Watch it: control packet (active_runs) or the Control Room; the broker validates the spec digest (${specSha.slice(0, 12)}…) and admission before the compose call. ` +
        `A queued submit is NOT a running run — verify the run row exists before treating the build as started.`,
      metadata: {
        job_id: jobMatch ? jobMatch[1] : "",
        spec: args.spec,
        spec_sha256: specSha,
        model: args.model,
        workdir: args.workdir,
        resume: args.resume,
        parent_run_id: args.parent_run_id ?? "",
        admission_required: admissionArmed,
        timestamp: new Date().toISOString(),
      },
    }
  },
})
