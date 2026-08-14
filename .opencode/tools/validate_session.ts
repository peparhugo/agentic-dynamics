import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Run pytest on generated code in a session worktree. Replaces heuristic correctness with actual test pass/fail.",
  args: {
    workdir: tool.schema.string().optional().describe("Path to session worktree"),
    session_id: tool.schema.string().optional().describe("OpenCode session ID"),
    model: tool.schema.string().optional().default("all").describe("Filter by model"),
  },
  async execute(args, ctx) {
    const flags: string[] = []
    if (args.workdir) flags.push("--workdir", args.workdir)
    if (args.session_id) flags.push("--session-id", args.session_id)
    if (args.model) flags.push("--model", args.model)

    const result = await Bun.$`python3 scripts/validate_session.py ${flags}`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0) {
      return { output: output || err || `validate_session failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
    }

    return {
      output: output || "Session validation complete.",
      metadata: { workdir: args.workdir ?? null, session_id: args.session_id ?? null, model: args.model, timestamp: new Date().toISOString() },
    }
  },
})
