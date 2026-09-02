## Claude Code

This repo is developed primarily through OpenCode (`.opencode/`, `AGENTS.md`, `opencode.json`).
The `.claude/` files are a parallel Claude Code surface **generated** from the neutral
`agent_config/` source by `scripts/_gen_instructions.py` (`render_claude()`) — never hand-edited
and never hand-synchronized; there is a build step. Edit `agent_config/`, then run
`python3 scripts/_gen_instructions.py`. See `docs/architecture/current/claude_code_port.md` for the
field-by-field mapping and the fields that don't cross the taxonomy (multi-provider
`model`/`small_model`, per-capability `permission`, `lsp`/`formatter`, `subagent_depth`).

The two ROOT documents are generated too. `AGENTS.md` is rendered from `agent_config/rules.md` and
this file is rendered from `agent_config/claude-code.md`, opening with Claude Code's `@AGENTS.md`
import — so the rules exist exactly once and the two roots cannot disagree. `--check` is the gate:
`python3 scripts/_gen_instructions.py --check` exits nonzero when any surface is stale, and CI runs
it on every push.

- `.claude/rules/*.md` — load unconditionally, rendered from the `agent_config/` instruction
  documents (the mental model and the conventions; the RULES arrive via the `@AGENTS.md` import
  above, so they are not duplicated here). They carry **stable** content only:
  architecture, authority, the command surface, and how to obtain dynamic state. Run state,
  spec-lifecycle counts, worktree ownership and deployment history are NOT here — that is what
  `agentic-dynamics control status --json` serves, on demand and current.
- `.claude/agents/*.md` — the subagents, rendered to `name` + `description` only. The opencode-only
  `mode`/`model`/`permission` fields are dropped by `render_claude()` — Claude subagents only select
  Claude models, and per-capability permissions have no subagent-frontmatter equivalent (the
  project-level `.claude/settings.json` holds those) — see the port doc.
- `.claude/commands/*.md` — the commands, rendered to `description` only (opencode-only
  `agent`/`subtask` dropped) with positional args re-indexed 1→0 by `render_claude()` (Claude's
  `$N` is 0-indexed where opencode's is 1-indexed; `$ARGUMENTS` matches on both).
- `.claude/skills/` — one `SKILL.md` per skill, rendered from `agent_config/skills/`; the
  name/description schema is shared, so both platforms get byte-identical skill text.
- `.opencode/tools/` has no 1:1 Claude Code file equivalent (no `.mcp.json` is shipped) — the tools'
  knowledge is carried by the skills/commands/`AGENTS.md`; invoke the underlying script directly via
  Bash per the relevant skill (see `docs/architecture/current/claude_code_port.md` §8 for the
  disposition).
- `.claude/settings.json` ports `opencode.json`'s `permission` block; `model`/`small_model`,
  `compaction.reserved`/`prune`, `subagent_depth`, `lsp`, `formatter` have no settings.json field
  and are not simulated — see the port doc.
