import { tool } from "@opencode-ai/plugin"

const BUILTIN_STORIES = ["task_manager_api", "static_site_gen", "notification_service"]
const CONDITIONS = ["clean", "bad_seed", "early_degrade", "late_degrade"]
const QUALITIES = ["good", "bad"]
const TIERS = ["tier1_minimal", "tier2_small"]
const BACKENDS = ["opencode", "claude_cli"]

export default tool({
  description: `Run a multi-session experiment story. Built-in stories: ${BUILTIN_STORIES.join(", ")}. Each story runs 5 sessions with git commits between each.`,
  args: {
    story: tool.schema.string().describe("Story name (task_manager_api, static_site_gen, notification_service) or path to custom YAML"),
    model: tool.schema.string().optional().default("deepseek/deepseek-v4-pro"),
    condition: tool.schema.enum(CONDITIONS as [string, ...string[]]).optional().default("clean"),
    codebase_quality: tool.schema.enum(QUALITIES as [string, ...string[]]).optional().default("good"),
    tier: tool.schema.enum(TIERS as [string, ...string[]]).optional().default("tier1_minimal"),
    timeout_min: tool.schema.number().optional().default(20),
    thinking_budget: tool.schema.number().optional().default(0),
    backend: tool.schema.enum(BACKENDS as [string, ...string[]]).optional().describe("Backend to execute sessions (default: auto routes anthropic/* to claude_cli)"),
    codebase: tool.schema.string().optional().describe("Path to seed codebase (overrides codebase_quality and tier)"),
    worktree_root: tool.schema.string().optional().describe("Parent directory for worktrees (default: /tmp)"),
    results_dir: tool.schema.string().optional().describe("Directory for result JSON files (default: experiments/results/stories)"),
    output_limit: tool.schema.number().optional().describe("Output token limit"),
    standardize: tool.schema.boolean().optional().default(true).describe("Apply standardized constraints (false → --no-standardize)"),
  },
  async execute(args, ctx) {
    if (!BUILTIN_STORIES.includes(args.story) && !args.story.includes("/") && !args.story.endsWith(".yaml")) {
      return `Unknown story: "${args.story}". Built-in stories: ${BUILTIN_STORIES.join(", ")}. Or provide a path to a custom YAML config.`
    }

    const flags = [
      "--model", args.model,
      "--condition", args.condition,
      "--codebase-quality", args.codebase_quality,
      "--tier", args.tier,
      "--timeout", String(args.timeout_min * 60),
    ]
    if (args.thinking_budget > 0) {
      flags.push("--thinking-budget", String(args.thinking_budget))
    }
    if (args.backend) flags.push("--backend", args.backend)
    if (args.codebase) flags.push("--codebase", args.codebase)
    if (args.worktree_root) flags.push("--worktree-root", args.worktree_root)
    if (args.results_dir) flags.push("--results-dir", args.results_dir)
    if (args.output_limit) flags.push("--output-limit", String(args.output_limit))
    if (!args.standardize) flags.push("--no-standardize")

    const result = await Bun.$`python3 scripts/run_story.py ${args.story} ${flags}`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()

    if (result.exitCode !== 0) {
      return { output: output || `Story failed (exit ${result.exitCode})`, metadata: { exit_code: result.exitCode } }
    }

    return {
      output: output.split("\n").slice(-5).join("\n") || `Story "${args.story}" completed`,
      metadata: {
        story: args.story, model: args.model, condition: args.condition,
        tier: args.tier, quality: args.codebase_quality, timestamp: new Date().toISOString(),
      },
    }
  },
})
