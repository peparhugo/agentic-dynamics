import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Build the Firebase website data.js from inventory and experiment results",
  args: {
    dry_run: tool.schema.boolean().optional().default(false),
  },
  async execute(args, ctx) {
    const flags = args.dry_run ? ["--dry-run"] : []

    const result = await Bun.$`python3 scripts/build_data.py ${flags}`.cwd(ctx.directory).quiet()
    const output = result.stdout.toString().trim()

    if (args.dry_run) {
      return { output: output || "Dry run complete. No files written.", metadata: { dry_run: true } }
    }
    return {
      output: output || "Data built successfully. Ready for firebase deploy --only hosting.",
      metadata: { timestamp: new Date().toISOString() },
    }
  },
})
