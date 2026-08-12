import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Check the status of background experiment runs (Redis queue + workers). Returns a progress matrix: total/queued/running/done/failed/timeout cells and results saved, broken down by story and condition.",
  args: {
    json: tool.schema
      .boolean()
      .optional()
      .default(true)
      .describe("Return machine-readable JSON (default true)"),
  },
  async execute(args, ctx) {
    const flags: string[] = []
    if (args.json) flags.push("--json")

    const result = await Bun.$`python3 scripts/monitor.py ${flags}`.cwd(ctx.directory).nothrow()

    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0) {
      return {
        output: output || err || "dashboard check failed",
        metadata: { exit_code: result.exitCode },
      }
    }

    return {
      output: output || "No experiment data",
      metadata: { timestamp: new Date().toISOString() },
    }
  },
})
