import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "List all available built-in stories (task_manager_api, static_site_gen, notification_service) with descriptions",
  args: {},
  async execute(_, ctx) {
    const result = await Bun.$`python3 scripts/run_story.py --list`.cwd(ctx.directory).quiet()
    return result.stdout.toString().trim()
  },
})
