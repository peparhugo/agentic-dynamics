import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Run parallel silent-mode sweep: 16 cells (4 models × 2 silent modes × 2 operators) with 4 concurrent workers",
  args: {},
  async execute(_, ctx) {
    const result = await Bun.$`python3 scripts/sweep_parallel.py`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()

    if (result.exitCode !== 0) {
      const stderr = result.stderr.toString().trim()
      return { output: output || `Sweep failed with exit code ${result.exitCode}`, metadata: { exit_code: result.exitCode, error: stderr } }
    }

    return {
      output: output || "Sweep completed. 16 cells across 4 models × 2 silent modes × 2 operators.",
      metadata: { cells: 16, models: 4, workers: 4, timestamp: new Date().toISOString() },
    }
  },
})
