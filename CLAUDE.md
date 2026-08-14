@AGENTS.md

## Claude Code

This repo is developed primarily through OpenCode (`.opencode/`, `AGENTS.md`, `opencode.json`).
The files below are a parallel Claude Code CLI surface, ported from the same corrected
opencode sources — see `docs/claude_code_port.md` for the full mapping, the fields that
don't cross the taxonomy (multi-provider `model`/`small_model`, per-capability `permission`,
`lsp`/`formatter`, `subagent_depth`), and the step-by-step recipe for re-porting after a
future opencode change. Keep both surfaces in sync by hand — there is no build step.

- `.claude/rules/mental-model.md`, `.claude/rules/conventions.md` — load unconditionally
  (no `paths:` frontmatter), same content as `.opencode/instructions/*.md`.
- `.claude/agents/*.md` — the 3 opencode subagents (`data-analysis`, `instrument-dev`,
  `pipeline-ops`), ported. Their opencode `model: deepseek/deepseek-v4-flash` has no Claude
  Code equivalent — Claude subagents only select Claude models — see the port doc.
- `.claude/commands/*.md` — the 5 opencode commands, flat 1:1, same `/name` invocation.
  `$ARGUMENTS` matches opencode's all-args form; numbered positional args do not — Claude
  Code's `$N` is 0-indexed where opencode's `$1`/`$2` is 1-indexed (`/run-exp` was adjusted
  for this; check any new numbered-arg command against the port doc).
- `.claude/skills/*/SKILL.md` — the 3 opencode skills (`analyze`, `instrument`, `lab-books`),
  ported verbatim.
- `.opencode/tools/*.ts` do **not** have a Claude Code file equivalent — they're thin
  `Bun.$` wrappers around `scripts/*.py` CLIs; invoke the underlying script directly via
  Bash instead. No `.mcp.json` is shipped (see the port doc's D1 rationale).
- `.claude/settings.json` ports `opencode.json`'s `permission` block; `model`/`small_model`,
  `compaction.reserved`/`prune`, `subagent_depth`, `lsp`, `formatter` have no settings.json
  field and are not simulated — see the port doc.
