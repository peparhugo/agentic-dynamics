import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Normalize story results into Parquet. sync (default) writes sessions.parquet + stories.parquet; check validates without writing; query runs read-only SQL over the synced data.",
  args: {
    mode: tool.schema.enum(["sync", "check", "query"]).optional().default("sync"),
    query: tool.schema.string().optional().describe("SQL to run (required when mode=query)"),
  },
  async execute(args, ctx) {
    if (args.mode === "query" && !args.query) {
      return "mode=query requires a `query` argument (SQL string)."
    }

    const flags: string[] = []
    if (args.mode === "check") flags.push("--check")
    if (args.mode === "query") flags.push("--query", args.query!)

    const result = await Bun.$`python3 scripts/sync_data.py ${flags}`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0) {
      return { output: output || err || `sync_data failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
    }

    return {
      output: output || `sync_data ${args.mode} completed`,
      metadata: { mode: args.mode, timestamp: new Date().toISOString() },
    }
  },
})
