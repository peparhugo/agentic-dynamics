import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Fill the Redis experiment queue with story job cells for parallel worker execution",
  args: {
    dry_run: tool.schema.boolean().optional().default(false),
    clear: tool.schema.boolean().optional().default(false),
    model: tool.schema.string().optional().describe("provider/model id to enqueue cells for (default: MODEL constant)"),
    missing_only: tool.schema.boolean().optional().default(false).describe("Only enqueue cells with no existing result"),
  },
  async execute(args, ctx) {
    if (args.clear && !args.dry_run) {
      return "WARNING: --clear will remove all pending jobs. To confirm, run again with clear=true and dry_run=true first to see what would be removed."
    }

    const flags = []
    if (args.dry_run) flags.push("--dry-run")
    if (args.clear && args.dry_run) flags.push("--clear")
    if (args.model) flags.push("--model", args.model)
    if (args.missing_only) flags.push("--missing-only")

    const result = await Bun.$`python3 scripts/enqueue.py ${flags}`.cwd(ctx.directory).quiet()
    return {
      output: result.stdout.toString().trim() || "Enqueue completed",
      metadata: { dry_run: args.dry_run, clear: args.clear, model: args.model ?? null, missing_only: args.missing_only },
    }
  },
})
