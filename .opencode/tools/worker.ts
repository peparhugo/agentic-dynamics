import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Manage Redis experiment workers: start a worker, check worker status, or stop all running workers",
  args: {
    action: tool.schema.enum(["start", "status", "stop"]).optional().default("status"),
  },
  async execute(args, ctx) {
    if (args.action === "start") {
      const result = await Bun.$`python3 scripts/worker.py &`.cwd(ctx.directory).nothrow()

      // Check if Redis is available
      const redisCheck = await Bun.$`python3 -c "
import redis, os
r = redis.Redis(host=os.environ.get('FINOPS_REDIS_HOST', '127.0.0.1'), port=int(os.environ.get('FINOPS_REDIS_PORT', 6379)), socket_connect_timeout=2)
print('connected' if r.ping() else 'no_ping')
"`.cwd(ctx.directory).nothrow().quiet()

      const redisStatus = redisCheck.stdout.toString().trim()
      if (redisStatus !== "connected") {
        return "Redis is not running. Start it with: docker compose -f infrastructure/docker-compose.experiment.yml up -d redis"
      }

      return "Worker started in background. Uses Redis at 127.0.0.1:6379. Auto-exits after 2 minutes of idle queue. Check progress with: monitor(action: 'status')"
    }

    if (args.action === "stop") {
      await Bun.$`pkill -f "scripts/worker.py" || true`.cwd(ctx.directory).quiet()
      return "Sent stop signal to all running workers."
    }

    // status
    const psCheck = await Bun.$`pgrep -f "scripts/worker.py" || true`.cwd(ctx.directory).quiet()
    const pids = psCheck.stdout.toString().trim()
    if (pids) {
      return `Workers running (PIDs: ${pids.split("\n").join(", ")}). Check queue status with monitor(action: 'status').`
    }
    return "No workers currently running."
  },
})
