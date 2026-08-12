import { tool } from "@opencode-ai/plugin"
import { existsSync, readdirSync } from "node:fs"
import { join } from "node:path"

export default tool({
  description: "Run a full perturbation experiment from a YAML config: baseline run then perturbed runs across all operators × strengths",
  args: {
    config: tool.schema.string().describe("Config name (e.g. baseline, url_shortener, task_manager) or path to YAML"),
    model: tool.schema.string().optional().describe("Model override in provider/model format (e.g. deepseek/deepseek-v4-pro)"),
    limit: tool.schema.number().optional().default(0).describe("Limit number of operators to test (0 = all)"),
    timeout_sec: tool.schema.number().optional().default(200).describe("Per-run timeout in seconds"),
    repetitions: tool.schema.number().optional().default(1),
  },
  async execute(args, ctx) {
    const configsDir = join(ctx.directory, "experiments", "configs")
    const configPath = args.config.includes("/") || args.config.includes(".yaml")
      ? args.config
      : join("experiments", "configs", args.config.endsWith(".yaml") ? args.config : `${args.config}.yaml`)

    if (!existsSync(join(ctx.directory, configPath))) {
      const yamlFile = args.config.endsWith(".yaml") ? args.config : `${args.config}.yaml`
      const fullPath = join(configsDir, yamlFile)
      if (!existsSync(fullPath)) {
        const available = readdirSync(configsDir)
          .filter((f) => f.endsWith(".yaml"))
          .map((f) => f.replace(".yaml", ""))
          .sort()
        return `Config not found: "${args.config}". Available: ${available.join(", ")}`
      }
    }

    const flags = []
    if (args.model) flags.push("--model", args.model)
    if (args.limit > 0) flags.push("--limit", String(args.limit))
    if (args.timeout_sec) flags.push("--timeout", String(args.timeout_sec))
    if (args.repetitions > 1) flags.push("--repetitions", String(args.repetitions))

    const result = await Bun.$`python3 scripts/run.py ${configPath} ${flags}`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()

    if (result.exitCode !== 0) {
      return { output: output || `Experiment failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
    }

    return {
      output: output.split("\n").slice(-5).join("\n") || "Experiment completed",
      metadata: { config: args.config, model: args.model || "default", timestamp: new Date().toISOString() },
    }
  },
})
