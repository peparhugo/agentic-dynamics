---
status: accepted
---
@AGENTS.md

## Claude Code

This repo is developed primarily through OpenCode (`.opencode/`, `AGENTS.md`, `opencode.json`).
The `.claude/` files are a parallel Claude Code surface **generated** from the neutral
`agent_config/` source by `scripts/_gen_instructions.py` (`render_claude()`) — never hand-edited
and never hand-synchronized; there is a build step. Edit `agent_config/`, then run
`python scripts/_gen_instructions.py`. See `docs/architecture/current/claude_code_port.md` for the field-by-field
mapping and the fields that don't cross the taxonomy (multi-provider `model`/`small_model`,
per-capability `permission`, `lsp`/`formatter`, `subagent_depth`).

- `.claude/rules/{mental-model,conventions,rules}.md` — load unconditionally (no `paths:`
  frontmatter), rendered from `agent_config/{mental-model,conventions,rules}.md`.
- `.claude/agents/*.md` — the 3 subagents (`data-analysis`, `instrument-dev`, `pipeline-ops`),
  rendered to `name` + `description` only. The opencode-only `mode`/`model`/`permission` fields are
  dropped by `render_claude()` — Claude subagents only select Claude models, and per-capability
  permissions have no subagent-frontmatter equivalent (the project-level `.claude/settings.json`
  holds those) — see the port doc.
- `.claude/commands/*.md` — the 5 commands, rendered to `description` only (opencode-only
  `agent`/`subtask` dropped) with positional args re-indexed 1→0 by `render_claude()` (Claude's
  `$N` is 0-indexed where opencode's is 1-indexed; `$ARGUMENTS` matches on both).
- `.claude/skills/{analyze,control-room,instrument,lab-books,queue,review,run-workflow}/SKILL.md` —
  the 7 skills, rendered from `agent_config/skills/`.
- `.opencode/tools/*.ts` have no 1:1 Claude Code file equivalent (no `.mcp.json` is shipped) — the
  tools' knowledge is carried by the skills/commands/`AGENTS.md`; invoke the underlying script
  directly via Bash per the relevant skill (see `docs/architecture/current/claude_code_port.md` §8 for the disposition).
- `.claude/settings.json` ports `opencode.json`'s `permission` block; `model`/`small_model`,
  `compaction.reserved`/`prune`, `subagent_depth`, `lsp`, `formatter` have no settings.json field
  and are not simulated — see the port doc.
