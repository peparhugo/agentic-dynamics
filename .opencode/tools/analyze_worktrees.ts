import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Run post-hoc analysis on all experiment worktrees: evaluate solutions, compute basin escape, generate GameReport markdown files",
  args: {},
  async execute(_, ctx) {
    const result = await Bun.$`python3 scripts/analyze_worktrees.py`.cwd(ctx.directory).quiet()
    const output = result.stdout.toString().trim()

    let summary = output
    if (!output) {
      summary = "Analysis completed. Check experiments/results/reports/ for GameReport markdown files and experiments/results/_results_summary.json for aggregate data."
    }
    return { output: summary, metadata: { timestamp: new Date().toISOString() } }
  },
})
