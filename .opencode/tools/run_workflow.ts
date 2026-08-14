import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Run an agent_task workflow (the execute phase of the spec/compiler DAG) against a goal inside a git worktree, committing + ledgering each phase.",
  args: {
    spec: tool.schema.string().describe("Path to an ExperimentSpec YAML"),
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
  },
  async execute(args, ctx) {
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
  },
})
