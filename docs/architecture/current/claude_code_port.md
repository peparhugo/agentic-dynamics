---
status: accepted
---
# OpenCode ↔ Claude Code Taxonomy Port

Living spec for porting this repo's OpenCode file-based configuration
(`AGENTS.md`, `.opencode/*`, `opencode.json`) to the Claude Code CLI taxonomy
(`CLAUDE.md`, `.claude/*`, `.mcp.json`), and back again after either side changes.
This is the fourth phase-doc in the opencode-docs-refresh chain
(`docs/website/opencode_docs_scope.md` → `docs/website/opencode_docs_challenge.md` →
`docs/website/opencode_docs_spec.md` §4 → this doc), and supersedes `docs/website/opencode_docs_spec.md`
§4's mapping table where the two disagree: this doc was written after fetching the
live docs a second time and generating the actual `.claude/*` files, so drift found
while doing that generation is corrected here rather than left standing in the spec.

**Gate for generating real `.claude/*` files (from `docs/website/opencode_docs_spec.md` D8,
now satisfied):** (1) the opencode drift-fix landed first (build-phase commit
`79fc6512e`) so there was one stable, correct source to translate, not two moving
targets; (2) an explicit instruction to port. Both are true as of this doc.

## 1. Sources fetched for this phase (2026-08-14)

Every fact below with a citation was pulled from a live `WebFetch`/`WebSearch` this
phase, not carried over from memory or an earlier phase's citation. Two general-purpose
research agents plus three direct fetches were used; URLs:

- OpenCode: `opencode.ai/docs/{agents,skills,commands,config,rules,custom-tools,mcp-servers,references}/`
- Claude Code: `code.claude.com/docs/llms.txt` (index), then
  `/docs/en/{cli-reference,memory,sub-agents,skills,settings,mcp,permissions}`

Where a fact could not be directly quoted (single-pass agent summary rather than a
verbatim excerpt this session pulled itself), it's marked **needs-verification** below
instead of **verified-against-docs**, per the same bar `opencode_docs_spec.md` used.

## 2. Verified mapping table

| OpenCode | Claude Code | Notes | Status |
|---|---|---|---|
| `AGENTS.md` (project root) | `CLAUDE.md` (project root) | Claude Code reads `CLAUDE.md`, not `AGENTS.md` — quoted directly: *"Claude Code reads CLAUDE.md, not AGENTS.md."* Documented pattern: `CLAUDE.md` starting with `@AGENTS.md` (import, expanded at launch), Claude-specific content appended below. A symlink (`ln -s AGENTS.md CLAUDE.md`) also works but needs admin/Dev Mode on Windows; the import has no such caveat. Target under 200 lines *for CLAUDE.md itself* — an imported file still loads in full, so this doesn't shrink the AGENTS.md content, it just avoids duplicating it. | **verified-against-docs** (`/docs/en/memory`, direct quote) |
| `.opencode/instructions/mental-model.md`, `conventions.md` | `.claude/rules/mental-model.md`, `.claude/rules/conventions.md` | Quoted: *"Rules without paths frontmatter are loaded at launch with the same priority as `.claude/CLAUDE.md`."* No frontmatter is required at all for an unscoped rule file — confirmed, not inferred. This is a closer match to opencode's `instructions: [...]` array (unconditional, always-loaded files) than folding the content into CLAUDE.md via `@import`, since CLAUDE.md has an explicit 200-line adherence guidance and these two files are 238 + 73 lines combined. | **verified-against-docs** (`/docs/en/memory` §"Organize rules with `.claude/rules/`", direct quote) |
| `.opencode/agents/*.md` (3: `data-analysis.md`, `instrument-dev.md`, `pipeline-ops.md`) | `.claude/agents/*.md` | Directory confirmed plural on both sides (`.opencode/agents/`, `.claude/agents/`). Claude subagent frontmatter, confirmed field-by-field: `name` (**required**, lowercase+hyphens, unique), `description` (**required**), `tools`, `disallowedTools`, `model` (`sonnet`\|`opus`\|`haiku`\|`fable`\|full ID\|`inherit`, default `inherit`), `permissionMode` (`default`\|`acceptEdits`\|`auto`\|`dontAsk`\|`bypassPermissions`\|`plan`\|`manual`), `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`, `initialPrompt`. Only `name`/`description` are required — every other opencode field (`mode`, `model`, `temperature`, `permission`, `color`, `hidden`) either has no Claude equivalent or maps to a *different-shaped* field (see row below). | **verified-against-docs** (`/docs/en/sub-agents`, exact field table quoted) |
| `.opencode/agent:model` (e.g. `deepseek/deepseek-v4-flash`) | `.claude/agents/*.md` `model:` | **Does not port — different universe of values, not a syntax difference.** opencode's `model` is an arbitrary `provider/model` string (any configured provider). Claude Code's `model:` only accepts a Claude alias (`sonnet`/`opus`/`haiku`/`fable`), a full Claude model ID, or `inherit`. There is no field anywhere in Claude Code that selects a non-Anthropic model for a subagent. Ported agents in this repo omit `model:` (default `inherit`) rather than inventing a fake value. | **verified-against-docs** (same page; absence confirmed by the field table having no open string type) |
| `.opencode/agent:permission` (`{edit, bash, task}` each `ask`\|`allow`\|`deny`) | `.claude/agents/*.md` `permissionMode` | **Shape mismatch, not a 1:1 port.** opencode gates each *capability* (edit/bash/task) independently. Claude's `permissionMode` is one enum for the whole subagent run (`default`, `acceptEdits`, `bypassPermissions`, etc.) — there's no per-capability equivalent at the subagent-frontmatter layer. This repo's 3 agents want `edit: ask, bash: allow, task: allow` (a mixed policy no single `permissionMode` expresses); ported agents leave `permissionMode` unset (session default) and rely on the project-level `.claude/settings.json` `permissions.allow` for the bash/task auto-run behavior instead — an approximation, not a faithful port. | needs-verification (mismatch itself is verified; the "rely on settings.json instead" workaround is this doc's judgment call, not a doc-confirmed equivalence) |
| `.opencode/commands/*.md` (5) | `.claude/commands/*.md` — flat, 1:1 | **Confirmed still fully supported, and confirmed to be the same underlying mechanism as skills, not a legacy path.** Quoted: *"Custom commands have been merged into skills. A file at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way. Your existing `.claude/commands/` files keep working."* Command frontmatter shares SKILL.md's field set *except* `name` and `paths`, which are ignored in a command file. This upgrades `opencode_docs_spec.md` §4's "needs-verification" status to fully verified — commands are not deprecated, and porting them flat (not into skill directories) is doc-supported, matching that doc's D2 decision for an independent reason (shared mechanism, not just "no bundled files to justify a directory"). | **verified-against-docs** (`/docs/en/skills`, direct quote) |
| `.opencode/command:agent`, `:subtask` | *(dropped, not mapped)* | opencode's `agent: build` names which opencode agent mode runs the command (opencode's built-in `build` primary mode ≈ full read/write agent — a concept with no Claude Code equivalent; Claude Code has no separate named "primary agent modes"). `subtask: true` requests running as a subagent task; the closest Claude field is a skill's `context: fork`, but fork changes user-visible behavior (separate context window) in a way this doc can't verify preserves the original commands' intent without testing. Both fields are dropped rather than guessed at — see `.claude/commands/*.md` in this repo, which ship with only `description:`. | needs-verification (dropped by choice, not confirmed absent — a future port could test `context: fork` against real command runs and promote this row) |
| `.opencode/command` positional args `$1`/`$2`/... | `.claude/commands/*.md` `$N` | **Same token, different index base — a correctness bug if copied verbatim.** Claude Code's `$N` is explicitly 0-indexed (*"`$N` (shorthand for `$ARGUMENTS[N]`, 0-indexed)"*): `$0`/`$1` is the first/second argument. opencode's positional args in this repo's own `run-exp.md` are 1-indexed shell-style (`$2` = second argument, per the file's own usage comment). Verbatim-copying `$2` into the Claude Code port would silently read the *third* argument instead of the second. This repo's `.claude/commands/run-exp.md` uses `$1` for that reason — confirmed load-bearing, not cosmetic. | **verified-against-docs** (`/docs/en/skills`, direct quote on 0-indexing) |
| `.opencode/skills/<name>/SKILL.md` (3: `analyze/`, `instrument/`, `lab-books/`) | `.claude/skills/<name>/SKILL.md` | Directory confirmed plural both sides. Both require `name` + `description` in frontmatter (opencode: 1–64 / 1–1024 chars, naming regex `^[a-z0-9]+(-[a-z0-9]+)*$`; Claude Code: `name` is technically optional — dir name is the command — but all 3 of this repo's skills already set it and satisfy the regex, so no rename needed either way). Claude Code additionally supports `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `effort`, `context`, `background`, `hooks`, `paths`, `shell` — none used by this repo's 3 skills, none required. | **verified-against-docs** (`/docs/en/skills`, field list quoted) |
| `.opencode/tools/*.ts` (16 existing + 9 designed in `opencode_docs_spec.md` §3.1 = 25) | **No MCP; ported as `.claude/skills/*/SKILL.md` files (net-new skills + fold-ins to the 3 existing skills).** | Confirmed: `.mcp.json` (project scope, `mcpServers` key) supports `stdio` (`command`/`args`/`env`), `http`/`streamable-http` (`url`/`headers`), and `ws` server shapes; `claude mcp add --transport stdio|http|sse` scaffolds an entry. **Per `opencode_docs_spec.md` D1 (reaffirmed, not reversed): none of the 25 tools is ported to MCP.** D1 rejected *MCP as the porting mechanism*, not porting the tools' knowledge at all — `docs/architecture/current/claude_tools_to_skills_scope.md` picked up the latter using the same file-based mechanism already used for `analyze`/`instrument`/`lab-books`: 4 net-new skill directories (`run-workflow`, `control-room`, `queue`, `review`) plus fold-ins of corrected flag knowledge into the 3 existing skills, for the tools whose exact flags/safety gates/lifecycle weren't yet documented anywhere in `.claude/`. Every one of the 25 tools is a thin `Bun.$`/HTTP wrapper around a `scripts/*.py` CLI or `admin/server.py` REST endpoint; a Claude Code agent with Bash access reproduces each one by invoking the script/`curl` directly per the skill's documented invocation — no MCP server, no new transport. **Still no `.mcp.json` shipped.** See §8 below for the full skill↔tool disposition table. | **verified-against-docs** (`.mcp.json` shape; `/docs/en/mcp`, direct); the skills-based resolution is this repo's own follow-up work (`docs/architecture/current/claude_tools_to_skills_scope.md`), not a doc-verified fact |
| `opencode.json` (root config) | `.claude/settings.json` (+ `.claude/settings.local.json` for personal overrides) | Both project-root JSON, both merge across scope layers. opencode: project/global/managed/remote. Claude Code (broadest→narrowest, confirmed): managed policy → user (`~/.claude/settings.json`) → project (`.claude/settings.json`) → local (`.claude/settings.local.json`, gitignored) → CLI flags. Port field-by-field, not verbatim — schemas aren't structurally identical (rows below). | **verified-against-docs** |
| `opencode.json:"model"` | `.claude/settings.json:"model"` | Both select a default model, but **the value spaces don't overlap**: opencode's is `provider/model` (this repo: `deepseek/deepseek-v4-pro`); Claude Code's `model` field is Claude-only (alias or full ID). **Not ported** — `.claude/settings.json` in this repo omits `model` entirely (session default applies) rather than substituting an unrelated Claude model as if it were equivalent. | **verified-against-docs** (field exists; value-space mismatch confirmed by the subagent `model:` field research, same constraint applies at the settings layer) |
| `opencode.json:"small_model"` | *(no equivalent field; closest is an env var, and the task's own draft citing it is stale)* | **Correction to this task's own draft mapping**, which suggested `ANTHROPIC_SMALL_FAST_MODEL`: that env var is confirmed **`[DEPRECATED]`** in the current CLI docs. Its replacement is `ANTHROPIC_DEFAULT_HAIKU_MODEL` (*"Model ID that the `haiku` alias resolves to, also used for background functionality"*), plus `_NAME`/`_DESCRIPTION`/`_SUPPORTED_CAPABILITIES`/`_AWS_REGION` variants. Even the replacement is a single global env var, not a per-project settings.json key, and (same as the `model` row) it only selects a Claude model — DeepSeek Flash has no destination field. Not set in this port. | **verified-against-docs** (`/docs/en/env-vars` via CLI reference fetch; `[DEPRECATED]` tag quoted directly) |
| `opencode.json:"instructions": [...]` | *(no equivalent field — mechanism mismatch)* | opencode requires an explicit file list. Claude Code auto-discovers `CLAUDE.md` + unscoped `.claude/rules/*.md` by directory convention (confirmed above) — there's no field to populate, the equivalent is just placing files at the conventional paths. Nothing to port beyond the two rows already covered (AGENTS.md→CLAUDE.md, instructions→rules/). | **verified-against-docs** |
| `opencode.json:"compaction": {auto, prune, reserved}` | `.claude/settings.json:"autoCompactEnabled"` (bool) + `"autoCompactWindow"` (int) / `/autocompact` | `auto` → `autoCompactEnabled` (both booleans, ported: `true`). `reserved` (opencode: token headroom to keep free) and `autoCompactWindow` (Claude: absolute token count at which compaction triggers) are **different units measuring different things**, not a direct numeric translation — `reserved: 15000` was **not** converted into a fabricated `autoCompactWindow` value; the field is left at Claude's own default. `prune` (whether compaction deletes vs. only summarizes) has **no confirmed Claude Code equivalent** — not set. | **verified-against-docs** (re-confirmed this phase via direct fetch of `/docs/en/settings`, not carried over from `opencode_docs_spec.md`'s earlier pass) |
| `opencode.json:"permission"` (nested: `edit`, `bash.*`, `task`, `external_directory`, `webfetch`, `skill`, each `allow`\|`ask`\|`deny`) | `.claude/settings.json:"permissions"` (`allow`/`deny`/`ask` arrays of `Tool` or `Tool(pattern)` strings) | **Confirmed exact translation semantics this phase** (`/docs/en/permissions`, direct fetch): a bare tool name (`"Bash"`) matches every call to that tool; `Tool(pattern)` scopes to a glob, e.g. `Bash(git push *)`; **rules are evaluated deny → ask → allow, first match wins regardless of specificity** — a matching `ask` rule prompts even when a broader `allow` rule also matches. This means opencode's `bash: {"*": "allow", "git push *": "ask", ...}` translates exactly: `"Bash"` in `allow` + `"Bash(git push *)"` in `ask` (not `deny` — `ask` preserves opencode's "prompt, don't block" semantics). Tool-name translation used for this repo: `edit`→`Edit`+`Write`+`NotebookEdit`, `bash`→`Bash`, `task`→**`Agent`** (Claude Code's subagent-launch tool is canonically named `Agent`, confirmed by the permission-doc's own examples `Agent(model:opus)`/`Agent(Explore)` — not `Task`, which is a different, unrelated canonical name (`TaskStop` etc.) the same docs page calls out explicitly), `webfetch`→`WebFetch`, `skill`→`Skill` (needs-verification — inferred from this session's own tool list, not from a permissions-page example naming the Skill tool specifically). `external_directory: allow` has no direct settings.json key of its own — see the `references` row below; this repo doesn't use opencode's `references`, so there's no directory list to carry over regardless. | **verified-against-docs** (pattern syntax, precedence, and the `Agent` vs `Task` canonical-name distinction all directly quoted from `/docs/en/permissions`) |
| *(not used in this repo)* `opencode.json:"references"` (`@alias`, local dirs or git repos) | `.claude/settings.json:"permissions.additionalDirectories"` | Confirmed: `--add-dir <path>` grants a session extra readable/editable directories; `permissions.additionalDirectories` in settings persists that grant across sessions — this is exactly what the CLI reference says `--add-dir` writes into. One added nuance beyond `opencode_docs_spec.md`'s pass: `.claude/agents/*.md` inside an added directory **is** scanned by default, but `CLAUDE.md` from an added directory is **not** loaded unless `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` is set — so the two file-taxonomy surfaces (subagents vs. memory) don't extend to an added directory symmetrically. This repo doesn't use `references` today (confirmed absent from `opencode.json`), so nothing populates `additionalDirectories` in this port. | **verified-against-docs** (re-confirmed this phase, added the asymmetric-loading nuance) |
| `opencode.json:"lsp": true`, `"formatter": true` | *(no equivalent)* | Confirmed absent from `.claude/settings.json`'s full field list this phase (`model`, `permissions.*`, `autoCompactEnabled`, `autoCompactWindow`, `claudeMd`, `claudeMdExcludes`, `autoMemoryEnabled`, `autoMemoryDirectory`, `agent`, `env`, plus managed-only/org fields) — no LSP-diagnostics or auto-formatting toggle anywhere in it. Claude Code's tool-use model relies on the agent invoking formatters/linters via Bash. Not simulated. | **verified-against-docs** (full settings field list fetched and enumerated this phase; absence confirmed, not just unfound) |
| `opencode.json:"subagent_depth": 2` | *(no equivalent)* | No field caps subagent nesting depth anywhere in the settings docs fetched this phase. Not simulated. | **verified-against-docs** (same full-field-list pass as above) |
| `opencode.json:"mcp"` (unused in this repo) | `.mcp.json` (project scope) | Both support local/remote server definitions in a different file from the main config. Not populated on either side — see the `.opencode/tools/*.ts` row for why this repo's port doesn't populate `.mcp.json` even though the file-type mapping itself is real. | **verified-against-docs** |
| *(no opencode equivalent — Claude-only)* | `~/.claude/projects/<project>/memory/*.md` (auto memory) | One-directional: Claude Code auto-writes durable, applicable lessons to a machine-local memory directory (`MEMORY.md` index + topic files, first 200 lines/25KB loaded at session start); opencode has no mechanism to port *from*. Noted for completeness — this session's own memory writes use exactly this mechanism. | **verified-against-docs** (this session's own memory system) |

## 3. Does-not-port-cleanly — summary list

For quick reference; each item is explained in its table row above.

1. **`.opencode/tools/*.ts` → MCP.** Nominal target exists (`.mcp.json`); recommended
   target remains "don't build an MCP server" (D1). The tools' *knowledge* — exact flags,
   safety gates, Redis lifecycle, background-job contracts — is ported separately, as
   `.claude/skills/*/SKILL.md` files (`docs/architecture/current/claude_tools_to_skills_scope.md`): Bash +
   these skills covers all 25 tools. See §8.
2. **`model`/`small_model` (multi-provider default model).** Claude Code's `model`
   fields (settings.json, subagent frontmatter) only accept Claude models. DeepSeek
   has no destination field anywhere in the taxonomy.
3. **Per-capability `permission` at the subagent level.** `permissionMode` is a single
   enum per subagent run; opencode's per-capability (`edit`/`bash`/`task`) grid has no
   subagent-frontmatter equivalent. (Project-level `permissions.allow`/`ask`/`deny` *does*
   port cleanly — see the `opencode.json:"permission"` row.)
4. **`opencode.json:"compaction".reserved` / `.prune`.** `reserved` (token headroom) and
   Claude's `autoCompactWindow` (absolute trigger point) are different units; `prune` has
   no confirmed equivalent at all.
5. **`lsp`/`formatter` toggles.** No settings.json field; Bash-invoked tooling only.
6. **`subagent_depth`.** No nesting-depth cap field.
7. **`.opencode/command:agent`/`:subtask`.** Dropped rather than approximated with
   `context: fork`, since fork changes user-visible behavior in a way not verified here.
8. **opencode's `instructions` array mechanism itself.** Not a missing field — Claude
   Code's directory-convention auto-discovery has nothing to configure.

## 4. Corrections to the task's own draft mapping

The task that requested this port included a draft mapping table as a starting point.
One row in that draft didn't survive verification against the live docs:

- Draft said: `opencode.json model/small_model -> model settings / ANTHROPIC_MODEL +
  ANTHROPIC_SMALL_FAST_MODEL`. **`ANTHROPIC_SMALL_FAST_MODEL` is confirmed
  `[DEPRECATED]`** in the current CLI/env-vars reference; its replacement is
  `ANTHROPIC_DEFAULT_HAIKU_MODEL`. Both are single global env vars, not project
  config, and (like `model` itself) only select a *Claude* model — neither is a real
  destination for opencode's DeepSeek default. See §2's `small_model` row.

Every other draft row held up under verification (some were upgraded from
"plausible" to **verified-against-docs** with a live citation; see §2).

## 5. Step-by-step port recipe

Repeatable procedure for re-running this port after either taxonomy changes (a new
opencode file type ships, a new Claude Code settings field ships, or this repo adds/
removes an agent, command, skill, or tool).

1. **Confirm the opencode source is current, not stale.** Diff `AGENTS.md`,
   `.opencode/instructions/*.md`, `.opencode/agents/*.md`, `.opencode/commands/*.md`,
   `.opencode/skills/*/SKILL.md`, `opencode.json` against the actual code they describe
   (module counts, script counts, flag lists, model names). Fix drift *before* porting —
   never translate a doc you know is wrong (this is `docs/website/opencode_docs_spec.md`'s D8
   gate #1, restated as a recipe step).
2. **Re-fetch both docs sets live**, don't rely on a prior phase's citations or model
   memory: `opencode.ai/docs/{agents,skills,commands,config,rules,custom-tools,
   mcp-servers,references}/` and `code.claude.com/docs/llms.txt` → the pages it
   indexes for memory, sub-agents, skills, settings, MCP, permissions, CLI reference.
   Docs move; a mapping verified 3 months ago can be stale (this phase itself
   corrected one field — see §4 — that an earlier phase's draft got wrong).
3. **Walk §2's table top to bottom** against the current repo state: for each opencode
   file/field, does its ported counterpart still exist with the fields this table
   claims? For each row marked **needs-verification**, treat it as an open item, not a
   settled fact, until directly re-confirmed.
4. **Generate files 1:1 per the table**, mirroring corrected content — do not
   paraphrase. Adapt only where the taxonomy forces it:
   - Frontmatter field names/values that don't exist on the target side (drop, don't
     invent — e.g. this repo's ported subagents omit `model:`/`permission:` rather
     than fabricating a Claude-model or single-mode substitute).
   - Cross-references to paths that moved (`.opencode/instructions/conventions.md` →
     `.claude/rules/conventions.md` inside the 3 ported agent files).
   - Indexing/semantic differences that would silently change behavior if copied
     verbatim (the `$1`/`$2` positional-arg base fix in `run-exp.md` — §2's dedicated
     row — is the canonical example; look for others any time a new templating
     feature is added on either side).
5. **Do not populate a taxonomy slot just because the row exists.** `.mcp.json` has a
   real, verified shape (§2) but this repo ships none — the row existing in the
   mapping table is not permission to invent content for it. Same discipline for any
   settings.json field with no verified opencode-side source value.
6. **Record every non-clean-port explicitly** (§3's list) rather than silently
   omitting the opencode capability. A future reader diffing the two taxonomies should
   be able to find *why* a field is missing on the Claude Code side, not have to
   rediscover it.
7. **Re-run this doc's own citations forward.** If a future opencode or Claude Code
   docs change invalidates a row, update that row's Status and Notes in place — this
   doc is meant to be edited, not re-written from scratch, on the next port.

## 6. What was generated this phase

| File | Source | Port notes |
|---|---|---|
| `CLAUDE.md` | `AGENTS.md` (imported via `@AGENTS.md`) + new Claude-specific pointer section | New content is a pointer/gap-summary only, not a paraphrase of AGENTS.md itself |
| `.claude/rules/mental-model.md` | `.opencode/instructions/mental-model.md` | Verbatim body + 1-line provenance header; no `paths:` frontmatter (unscoped, loads like CLAUDE.md) |
| `.claude/rules/conventions.md` | `.opencode/instructions/conventions.md` | Verbatim body + 1-line provenance header |
| `.claude/agents/data-analysis.md`, `instrument-dev.md`, `pipeline-ops.md` | `.opencode/agents/*.md` | `name`/`description` frontmatter only; `model`/`permission` dropped with an inline note (§2); one internal path fixed per file (`conventions.md` cross-reference) |
| `.claude/commands/analyze.md`, `lab.md`, `new-exp.md`, `pipeline.md`, `run-exp.md` | `.opencode/commands/*.md` | `description` frontmatter only; `agent`/`subtask` dropped (§2); `run-exp.md`'s `$2` → `$1` (§2, load-bearing) |
| `.claude/skills/analyze/SKILL.md`, `instrument/SKILL.md`, `lab-books/SKILL.md` | `.opencode/skills/*/SKILL.md` | Verbatim at the time of this phase — later extended with corrected `.opencode/tools/*.ts` knowledge; see §8 |
| `.claude/skills/run-workflow/SKILL.md`, `control-room/SKILL.md`, `queue/SKILL.md`, `review/SKILL.md` | `.opencode/tools/*.ts` (9 of 25, net-new) | New phase, not part of the original taxonomy port — see §8 |
| `.claude/settings.json` | `opencode.json`'s `permission` block + `compaction.auto` | See §2's `permission` and `compaction` rows for the exact translation; `model`, `small_model`, `compaction.reserved`/`.prune`, `subagent_depth`, `lsp`, `formatter`, `references`/`additionalDirectories` (unused) all intentionally absent |
| `.mcp.json` | *(not generated)* | Per §2/§3 — no opencode tool warrants an MCP server; generating an empty or placeholder file would misrepresent a decision as a limitation |

## 7. Re-verification checklist for the next port

- [ ] Diff this table's file list against `find .opencode -type f -not -path
      '*/node_modules/*'` and `.claude/` — new files on either side need a new row.
- [ ] Re-fetch `code.claude.com/docs/llms.txt` and check for new pages not in §1's list
      (Claude Code ships new docs pages between phases; e.g. `permissions.md` wasn't in
      `opencode_docs_spec.md`'s original fetch set and turned out to hold the
      load-bearing precedence/pattern facts for the `permission` row).
- [ ] Re-fetch `opencode.ai/docs/config/` and `/docs/references/` — confirm `references`
      is still a separate page from `/docs/config/` (it was this phase) before assuming
      its absence from `/docs/config/`'s fetch means the feature doesn't exist.
- [ ] Spot-check any settings.json field this doc marked "no equivalent" — a negative
      claim is only as good as the fetch that produced it; re-search before repeating it.
- [ ] If `opencode.json` gains a `references` entry (this repo doesn't use it today),
      populate `permissions.additionalDirectories` for real and re-test the
      `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` asymmetry noted in §2.

## 8. `.opencode/tools/*.ts` → skills split (later phase)

A later phase, scoped and executed in `docs/architecture/current/claude_tools_to_skills_scope.md`, closed the
gap this doc's §2 `.opencode/tools/*.ts` row and §3 item 1 originally left open: D1 said
"don't build an MCP server," but the 25 tools' own knowledge (exact flags verified against
each script's `argparse`/`sys.argv`, safety gates like `enqueue.py --clear` requiring
`--dry-run` first, Redis queue lifecycle ordering, the `admin/server.py` read-only/observe-
only boundary) wasn't yet captured anywhere in `.claude/`. That phase read every
`.opencode/tools/*.ts` file and its backing `scripts/*.py`/`admin/server.py` source directly
(not the existing skills' prose) and produced this disposition, split three ways:

| Disposition | Count | Where |
|---|---|---|
| **NET-NEW** — dedicated skill, no existing skill covers it | 9 | `run-workflow` (`compile_experiment.ts`, `run_workflow.ts`), `control-room` (`control_room.ts`, `supervisor.ts`), `queue` (`enqueue.ts`, `worker.ts`, `monitor.ts`, `dashboard.ts`), `review` (`review.ts`) |
| **FOLD** — existing skill already documents the script, sometimes incorrectly; corrected/extended in place | 10 | `run_experiment.ts`, `run_story.ts`, `batch.ts`, `sweep.ts` → `instrument`; `analyze_worktrees.ts`, `analyze_trajectories.ts`, `sync_data.ts`, `build_data.ts`, `validate_session.ts` → `analyze`; `run_lab.ts` → `lab-books` |
| **SKIP** — already fully covered by a command, `AGENTS.md`, or an existing skill section; no new content needed | 6 | `pipeline.ts`, `inventory.ts`, `backfill.ts`, `archive_worktrees.ts`, `generate_manifest.ts`, `list_stories.ts` |

Three corrections surfaced during the fold that predate this split and aren't caused by
it — pre-existing wrong examples in the ported skills, fixed as part of folding in the
tool that would have otherwise repeated them: `instrument/SKILL.md`'s
`python scripts/run.py --config ...` examples (`config` is positional, no `--config` flag
exists — `scripts/run.py:488`) and its `run_story.py --story ...` examples (`story` is
also positional, not `--story` — `scripts/run_story.py:45-49`); `analyze/SKILL.md`'s
`validate_session.py --worktree ...` example (the real flag is `--workdir` —
`scripts/validate_session.py:83`). Full verification detail, exact invocations, and the
per-tool reasoning: `docs/architecture/current/claude_tools_to_skills_scope.md`.

`.opencode/tools/*.ts` itself was not touched by this split — opencode's tools stay as-is;
only the Claude Code-side knowledge changed.
