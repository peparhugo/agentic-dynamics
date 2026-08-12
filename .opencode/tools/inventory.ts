import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Query the experiment inventory: refresh, list experiments, show stats, list worktrees, or generate reports",
  args: {
    action: tool.schema.enum(["stats", "list", "worktrees", "refresh", "report"]),
    verbose: tool.schema.boolean().optional().default(false),
    show_all_worktrees: tool.schema.boolean().optional().default(false),
  },
  async execute(args, ctx) {
    const flags = []
    if (args.verbose) flags.push("-v")
    if (args.show_all_worktrees && args.action === "worktrees") flags.push("-a")

    const result = await Bun.$`python3 scripts/inventory.py ${args.action} ${flags}`.cwd(ctx.directory).quiet()
    return {
      output: result.stdout.toString().trim() || `inventory ${args.action} completed`,
      metadata: { action: args.action, timestamp: new Date().toISOString() },
    }
  },
})
