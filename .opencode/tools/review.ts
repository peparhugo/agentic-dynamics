import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Review generated code across stories. all runs review_all.py (ThreadPoolExecutor, no Redis, synchronous). stories runs review_stories.py (batch commit + story review). trigger spawns Redis review workers and returns immediately (background, like worker start). enqueue pushes review jobs to Redis. finalize merges per-session review files into aggregates.",
  args: {
    action: tool.schema.enum(["all", "stories", "trigger", "enqueue", "finalize"]).optional().default("all"),
    workers: tool.schema.number().optional().describe("Worker count (action=all: --workers; action=trigger: REVIEW_WORKERS env)"),
    story: tool.schema.string().optional().describe("Substring filter on story name (action=all only)"),
    dry_run: tool.schema.boolean().optional().default(false),
  },
  async execute(args, ctx) {
    if (args.action === "all") {
      const flags: string[] = []
      if (args.workers) flags.push("--workers", String(args.workers))
      if (args.story) flags.push("--story", args.story)
      if (args.dry_run) flags.push("--dry-run")

      const result = await Bun.$`python3 scripts/review_all.py ${flags}`.cwd(ctx.directory).nothrow()
      const output = result.stdout.toString().trim()
      if (result.exitCode !== 0) {
        return { output: output || `review_all failed (exit ${result.exitCode})`, metadata: { action: "all", exit_code: result.exitCode } }
      }
      return { output: output || "Review (all) complete.", metadata: { action: "all", workers: args.workers ?? null, story: args.story ?? null, dry_run: args.dry_run } }
    }

    if (args.action === "stories") {
      const flags: string[] = []
      if (args.dry_run) flags.push("--dry-run")
      const result = await Bun.$`python3 scripts/review_stories.py ${flags}`.cwd(ctx.directory).nothrow()
      const output = result.stdout.toString().trim()
      if (result.exitCode !== 0) {
        return { output: output || `review_stories failed (exit ${result.exitCode})`, metadata: { action: "stories", exit_code: result.exitCode } }
      }
      return { output: output || "Review (stories) complete.", metadata: { action: "stories", dry_run: args.dry_run } }
    }

    if (args.action === "trigger") {
      // Spawns background review workers via Redis; returns immediately, work continues async
      // (same contract as worker.ts action:"start" — this does not block on completion).
      const env = args.workers ? { ...process.env, REVIEW_WORKERS: String(args.workers) } : process.env
      await Bun.$`python3 scripts/trigger_reviews.py &`.cwd(ctx.directory).env(env).nothrow()
      return {
        output: `Review workers triggered (${args.workers ?? 4} workers). Runs in the background — check progress via monitor(action:'status').`,
        metadata: { action: "trigger", workers: args.workers ?? 4 },
      }
    }

    if (args.action === "enqueue") {
      const flags: string[] = []
      if (args.dry_run) flags.push("--dry-run")
      const result = await Bun.$`python3 scripts/enqueue_reviews.py ${flags}`.cwd(ctx.directory).nothrow()
      const output = result.stdout.toString().trim()
      if (result.exitCode !== 0) {
        return { output: output || `enqueue_reviews failed (exit ${result.exitCode})`, metadata: { action: "enqueue", exit_code: result.exitCode } }
      }
      return { output: output || "Review jobs enqueued.", metadata: { action: "enqueue", dry_run: args.dry_run } }
    }

    // finalize
    const result = await Bun.$`python3 scripts/finalize_reviews.py`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()
    if (result.exitCode !== 0) {
      return { output: output || `finalize_reviews failed (exit ${result.exitCode})`, metadata: { action: "finalize", exit_code: result.exitCode } }
    }
    return { output: output || "Reviews finalized.", metadata: { action: "finalize" } }
  },
})
