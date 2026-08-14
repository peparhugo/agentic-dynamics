import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Parse session.jsonl transcripts into step-level trajectory metrics. Produces _trajectory_summary.json (per-transcript) and _trajectory_aggregate.json (per-model).",
  args: {
    limit: tool.schema.number().optional().describe("Max transcripts to process (default: all)"),
    model: tool.schema.string().optional().describe("Filter by model name (e.g. deepseek, claude)"),
    dry_run: tool.schema.boolean().optional().default(false).describe("Print instead of writing"),
  },
  async execute(args, ctx) {
    const flags: string[] = []
    if (args.limit) flags.push("--limit", String(args.limit))
    if (args.model) flags.push("--model", args.model)
    if (args.dry_run) flags.push("--dry-run")

    const result = await Bun.$`python3 scripts/analyze_trajectories.py ${flags}`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0) {
      return { output: output || err || `analyze_trajectories failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
    }

    return {
      output: output || "Trajectory analysis complete.",
      metadata: { limit: args.limit ?? null, model: args.model ?? null, dry_run: args.dry_run, timestamp: new Date().toISOString() },
    }
  },
})
