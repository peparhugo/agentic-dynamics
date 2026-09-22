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
unbound consequential submit at the backend itself, with or without the plugin loaded — is
**implemented (Unit D) and live**: the submit contract
(`scripts/fleet/spawn_wrapper.py`'s `_validate_aio_binding`, invoked by `validate-submit`) is
re-run STRICTLY by the host launch broker before the launch effect, and it resolves the binding
from the durable store **by native session id** — a claimed `binding_id` is never proof: the
resolved agent, the authorization identity, the task revision, and the binding's project must
all match the store, or the submit is refused by name. Conversation capacity is attached as an
ADVISORY verdict only (2026-09-16 policy) — never an authorization field.

Live-proven 2026-09-22 (both directions, against the real store):

* a forged `binding_id` → `validate-submit` refuses: *"aio.binding_id 000000000000… does not
  match the binding's authorization identity c5d2c2031cf4… — a claimed id is not proof of
  binding"*;
* the genuine binding → `ok: true`, with `aio_capacity: {verdict: OK, advisory: true}`.

An absent or failed plugin still degrades to thinner context — and now the backend refusal
stands on its own, which is what makes the binding an authorization rather than a convention.
