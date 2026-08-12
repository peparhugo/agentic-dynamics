import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Run or inspect a pipeline plan (YAML-driven phase orchestration). Plans: ci (lint→test→build), deploy (refresh→sync→build→deploy), full_matrix (experiment matrix→analyze→review→regenerate→deploy), feature (spec→implement→lint→test→review→ship), ship_features (parallel workstreams→conflict detect→PR create→merge)",
  args: {
    action: tool.schema
      .enum(["run", "dry_run", "graph", "status", "reset", "check_deps"])
      .optional()
      .default("run")
      .describe("run executes the plan, dry_run previews the DAG, graph prints the dependency tree, status shows Redis state, reset clears Redis state, check_deps validates the DAG"),
    plan: tool.schema
      .string()
      .optional()
      .default("ci")
      .describe("Plan name: ci, deploy, full_matrix, feature, or ship_features"),
    from_phase: tool.schema.string().optional().describe("Start execution from this phase id"),
    until_phase: tool.schema.string().optional().describe("Stop execution after this phase id"),
    only_phases: tool.schema.string().optional().describe("Comma-separated subset of phase ids to run"),
    prompt: tool.schema.string().optional().describe("Value substituted for {prompt} placeholders in phase commands (feature/ship_features plans)"),
    workers: tool.schema.number().optional().describe("Override the worker count for matrix/review/fan_out phases"),
  },
  async execute(args, ctx) {
    const flags = ["--plan", args.plan]

    switch (args.action) {
      case "dry_run":
        flags.push("--dry-run")
        break
      case "graph":
        flags.push("--graph")
        break
      case "status":
        flags.push("--status")
        break
      case "reset":
        flags.push("--reset")
        break
      case "check_deps":
        flags.push("--check-deps")
        break
      case "run":
        break
    }

    if (args.from_phase) flags.push("--from", args.from_phase)
    if (args.until_phase) flags.push("--until", args.until_phase)
    if (args.only_phases) flags.push("--only", args.only_phases)
    if (args.prompt) flags.push("--prompt", args.prompt)
    if (args.workers && args.workers > 0) flags.push("--workers", String(args.workers))

    const result = await Bun.$`python3 scripts/pipeline.py ${flags}`.cwd(ctx.directory).nothrow()

    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0) {
      return {
        output: output || err || `pipeline ${args.action} failed (exit ${result.exitCode})`,
        metadata: { action: args.action, plan: args.plan, exit_code: result.exitCode },
      }
    }

    return {
      output: output || `Pipeline ${args.action} completed for plan '${args.plan}'`,
      metadata: { action: args.action, plan: args.plan, timestamp: new Date().toISOString() },
    }
  },
})
