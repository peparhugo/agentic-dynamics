import { tool } from "@opencode-ai/plugin"
import { readdirSync } from "node:fs"
import { join } from "node:path"

export default tool({
  description: "Run a lab book analysis",
  args: {
    lab: tool.schema.string().describe("Lab name (e.g. grit_matrix, flail_triggers, survival_horizon)"),
    max_steps: tool.schema.number().optional().default(0),
  },
  async execute(args, ctx) {
    const scriptsDir = join(ctx.directory, "scripts")
    let validLabs: string[] = []
    try {
      validLabs = readdirSync(scriptsDir)
        .filter((f) => f.startsWith("lab_") && f.endsWith(".py") && !f.includes("DEPRECATED"))
        .map((f) => f.replace("lab_", "").replace(".py", ""))
    } catch {
      // proceed without validation
    }

    if (validLabs.length > 0 && !validLabs.includes(args.lab)) {
      return `Unknown lab: "${args.lab}". Available: ${validLabs.sort().join(", ")}`
    }

    const extraArgs = args.max_steps && args.max_steps > 0 ? [`--max-steps`, String(args.max_steps)] : []

    const result = await Bun.$`python3 scripts/lab_${args.lab}.py ${extraArgs}`.cwd(ctx.directory).quiet()
    return {
      output: result.stdout.toString().trim() || `lab "${args.lab}" completed`,
      metadata: { lab: args.lab, timestamp: new Date().toISOString() },
    }
  },
})
