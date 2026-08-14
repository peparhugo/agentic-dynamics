import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Run parallel batch experiments across a fixed 13-config subset (scripts/batch_run.py:CONFIGS — not all 34 configs in experiments/configs/) using DeepSeek V4 Pro with 3 concurrent workers",
  args: {},
  async execute(_, ctx) {
    const result = await Bun.$`python3 scripts/batch_run.py`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()

    if (result.exitCode !== 0) {
      const stderr = result.stderr.toString().trim()
      return { output: output || `Batch failed with exit code ${result.exitCode}`, metadata: { exit_code: result.exitCode, error: stderr } }
    }

    return {
      output: output || "Batch completed. Results saved to /tmp/batch_deepseek_results.json.",
      metadata: { configs: 13, workers: 3, timestamp: new Date().toISOString() },
    }
  },
})
