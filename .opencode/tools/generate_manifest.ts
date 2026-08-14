import { tool } from "@opencode-ai/plugin"

export default tool({
  description:
    "Generate data_manifest.json — schema version, file SHA256s, git commit, opencode version, known limitations. Takes no flags.",
  args: {},
  async execute(_, ctx) {
    const result = await Bun.$`python3 scripts/generate_manifest.py`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0) {
      return { output: output || err || `generate_manifest failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
    }

    return {
      output: output || "data_manifest.json generated.",
      metadata: { timestamp: new Date().toISOString() },
    }
  },
})
