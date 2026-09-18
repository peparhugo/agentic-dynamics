# `.opencode/plugins/` — hand-authored, outside the generator

This directory holds OpenCode project plugins. Like `.opencode/tools/`, it is **hand-authored
and deliberately outside the generated-surface set**: the generator
(`scripts/_gen_instructions.py`, `agent_config/` → `.opencode/` + `.claude/` + the root files)
does not own it, and its freshness check does not cover it. Edit plugin files directly; keep
their tests outside auto-loaded directories (e.g. `tests/opencode/`).

The approved AIO capsule plugin **lives here** (`aio-context.ts` — automatic identity binding
+ capsule injection); the controller approved its scope on 2026-09-14. It is auto-loaded from
this directory (opencode ≥1.18 supports both `.opencode/plugin/` and `.opencode/plugins/` as
loader locations).

**The explicit handoff attachment.** When `.opencode/aio-task-context.json` exists in the
project, the plugin attaches it to the session's binding on the first substantive message:
`native_session_id` (REQUIRED for an initial handoff — a fresh session cannot validate a
task reference against an identity it does not have yet), `task` (stable identity),
`predecessor_slug` + `knowledge_ids` (the explicitly selected origin and findings),
`acceptance` (+ `acceptance_source`/`acceptance_provenance`), `project`, `source_revision`,
`work_unit`, `next_action`, `blocker`, and `context_version`. Task/project references remain
valid for UPDATES, where the session's bound identity is there to compare against.
The file is the EXPLICIT selection — the plugin never invents one. Raise `context_version`
to apply an update; the original request is immutable and no update can replace it.

**The snapshot delivery (2026-09-17 cache repair).** The capsule snapshot is delivered as a
synthetic TEXT PART attached to the incoming user message (`chat.message` → `output.parts`),
which the runtime persists with the message — a persisted context message that every later
request re-sends byte-identically (verified end-to-end against the deployed runtime). The
system prompt carries ONE static line; `experimental.chat.messages.transform` appends a
trailing snapshot when the request's latest user message has no SUCCESSFUL snapshot — the
post-compaction synthetic continuation, restored messages, legacy histories, or an
UNAVAILABILITY notice from a transient failure (which must not block automatic recovery: the
next request retries and appends the recovered capsule) — and
`experimental.session.compacting` carries the capsule into the compaction prompt. Every
delivery is journaled to `.opencode/aio-context-events.jsonl` (including the user message id
it serves) for `agentic-dynamics session cache-report`.

**Enforcement status.** The plugin's `tool.execute.before` refusal is a convenience and an
early warning only — it is not the safety property. The REQUIRED enforcement — refusing an
unbound consequential submit at the backend itself (submit contract, admission, promote
gate), with or without the plugin loaded) — is **Unit D behavior and is NOT implemented yet**.
An absent or failed plugin degrades to thinner context, and there is NO backend binding
refusal to fall back on. Do not describe the plugin as authority, and do not claim
enforcement that is not present.
