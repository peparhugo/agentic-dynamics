import { tool } from "@opencode-ai/plugin"
import { readdirSync, existsSync } from "node:fs"
import { execSync } from "node:child_process"
import { join } from "node:path"

export default tool({
  description: "Archive experiment worktrees from /tmp into git history under refs/experiments/. Safe by default — never deletes without explicit confirmation.",
  args: {
    pattern: tool.schema.enum(["exp", "story", "all"]).optional().default("all"),
    remove_after: tool.schema.boolean().optional().default(false),
    dry_run: tool.schema.boolean().optional().default(true),
  },
  async execute(args, ctx) {
    const tmpDir = "/tmp"
    const globs = args.pattern === "all"
      ? ["exp_*", "story_*"]
      : [`${args.pattern}_*`]

    let entries: string[] = []
    try {
      entries = readdirSync(tmpDir)
    } catch {
      return "Cannot read /tmp"
    }

    const matches: { name: string; hasGit: boolean }[] = []
    for (const entry of entries) {
      const matchPattern = globs.some((g) => {
        const regex = new RegExp("^" + g.replace("*", ".*") + "$")
        return regex.test(entry)
      })
      if (!matchPattern) continue
      const fullPath = join(tmpDir, entry)
      if (!existsSync(join(fullPath, ".git"))) continue
      matches.push({ name: entry, hasGit: true })
    }

    if (matches.length === 0) {
      return `No ${args.pattern} worktrees with git history found in /tmp.`
    }

    if (args.dry_run) {
      const lines = [`Dry run: ${matches.length} worktrees would be archived to refs/experiments/:`]
      for (const m of matches) {
        lines.push(`  ${m.name}`)
      }
      if (!args.remove_after) {
        lines.push(`\nWorktrees will be preserved in /tmp after archiving (remove_after=false).`)
      } else {
        lines.push(`\nWorktrees WILL be removed from /tmp after archiving (remove_after=true).`)
      }
      lines.push(`\nRun with dry_run=false to execute.`)
      return { output: lines.join("\n"), metadata: { count: matches.length } }
    }

    const archived: string[] = []
    const skipped: string[] = []
    const errors: string[] = []

    for (const m of matches) {
      const refName = `refs/experiments/${m.name}`
      const worktreePath = join(tmpDir, m.name)

      // Check if this ref already exists (skip re-archive)
      try {
        execSync(`git show-ref --verify --quiet "${refName}"`, { encoding: "utf-8", cwd: ctx.directory })
        skipped.push(`${m.name} (already archived)`)
        continue
      } catch {
        // ref doesn't exist, proceed
      }

      // Check if worktree has any commits
      let hasCommits = false
      try {
        const branch = execSync(`git -C "${worktreePath}" rev-parse --abbrev-ref HEAD`, { encoding: "utf-8" }).trim()
        execSync(`git -C "${worktreePath}" rev-parse --verify HEAD`, { encoding: "utf-8" })
        try {
          execSync(`git fetch "${worktreePath}" "+${branch}:${refName}"`, { encoding: "utf-8", cwd: ctx.directory })
          archived.push(m.name)
          hasCommits = true
        } catch (e) {
          errors.push(`${m.name}: fetch failed (${(e as Error).message.slice(0, 80)})`)
        }
      } catch {
        skipped.push(`${m.name} (no commits)`)
      }

      // Optionally remove worktree from /tmp
      if (hasCommits && !errors.includes(m.name) && args.remove_after) {
        try {
          execSync(`rm -rf "${worktreePath}"`, { encoding: "utf-8" })
        } catch {
          // not fatal
        }
      }
    }

    const lines: string[] = []
    if (archived.length > 0) {
      lines.push(`Archived ${archived.length} worktrees to refs/experiments/.`)
      lines.push(`  Browse: git log refs/experiments/{name}`)
      lines.push(`  List all: git for-each-ref refs/experiments/`)
    }
    if (skipped.length > 0) {
      lines.push(`Skipped ${skipped.length}: ${skipped.join(", ")}`)
    }
    if (errors.length > 0) {
      lines.push(`Errors (${errors.length}): ${errors.join("; ")}`)
    }
    if (args.remove_after && archived.length > 0) {
      lines.push(`Removed ${archived.length} worktrees from /tmp.`)
    }

    return {
      output: lines.join("\n") || "Archive completed.",
      metadata: { archived: archived.length, skipped: skipped.length, errors: errors.length },
    }
  },
})
