import { tool } from "@opencode-ai/plugin"

// SECURITY CONSTRAINT (do not weaken): this tool exposes only the --once flag-and-observe
// path of scripts/supervise.py. src/instrument/supervisor.py deliberately has no OpenCode
// client dependency "so observation can't become control" — never add a mode, flag, or
// follow-up tool here that lets an agent steer or interrupt a session. That capability
// exists only at admin/server.py's human-operated POST /api/flags/<id>/steer and
// /interrupt routes, which control_room.ts also must not wrap.
export default tool({
  description:
    "Run one supervisor assessment pass over running opencode sessions via a flash monitor session (flag-only — observe, never steer). Wraps scripts/supervise.py.",
  args: {
    once: tool.schema.boolean().optional().default(true).describe("Run one assessment pass and exit (the only supported mode — this tool never runs a continuous/steering loop)"),
    location: tool.schema.string().optional().describe("Repo location for the monitor session (default: current directory)"),
  },
  async execute(args, ctx) {
    const flags: string[] = []
    if (args.once) flags.push("--once")
    flags.push("--location", args.location ?? ctx.directory)

    const result = await Bun.$`python3 scripts/supervise.py ${flags}`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0) {
      return { output: output || err || `supervisor pass failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
    }

    return {
      output: output || "Supervisor assessment pass complete.",
      metadata: { once: args.once, location: args.location ?? ctx.directory, timestamp: new Date().toISOString() },
    }
  },
})
