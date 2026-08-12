import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Backfill artifact directories: copy generated code from /tmp/exp_* worktrees to experiments/results/reports/",
  args: {
    dry_run: tool.schema.boolean().optional().default(false),
    sessions_only: tool.schema.boolean().optional().default(false),
    worktree: tool.schema.string().optional().describe("Single worktree name (e.g. exp_abc123)"),
  },
  async execute(args, ctx) {
    const flags = []
    if (args.dry_run) flags.push("--dry-run")
    if (args.sessions_only) flags.push("--sessions-only")
    if (args.worktree) flags.push("--worktree", args.worktree)

    const result = await Bun.$`python3 scripts/backfill_artifacts.py ${flags}`.cwd(ctx.directory).quiet()
    return {
      output: result.stdout.toString().trim() || "Backfill completed",
      metadata: { dry_run: args.dry_run, sessions_only: args.sessions_only },
    }
  },
})
