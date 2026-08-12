import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Monitor Redis experiment queue: show job status, watch live progress, or clear experiment data",
  args: {
    action: tool.schema.enum(["status", "watch", "clear"]).optional().default("status"),
  },
  async execute(args, ctx) {
    if (args.action === "clear") {
      return "WARNING: --clear removes all experiment data from Redis. To confirm, run monitor.py --clear manually from the terminal."
    }

    if (args.action === "watch") {
      return "Live monitoring requires an interactive terminal. Run `python3 scripts/monitor.py --watch` in your terminal to watch live progress."
    }

    const result = await Bun.$`python3 scripts/monitor.py`.cwd(ctx.directory).quiet()
    return result.stdout.toString().trim() || "No active experiment data in Redis."
  },
})
