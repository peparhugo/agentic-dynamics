---
name: knowledge-reader
description: How a step reads the knowledge base with its own scope — the read contract (scope rules, the `knowledge read` verb, deterministic artifact search, ranked retrieval, authority/lifecycle etiquette, and the zero-hit scope gotcha). Use when a step, session, or agent needs to retrieve prior findings, decisions, sessions, or code knowledge from the KB, or to answer "what do we retrieve".
disable-model-invocation: false
user-invocable: false
argument-hint: ""
---

# Knowledge Reader Skill — given a scope, read the KB

## The scope contract (read it first)

Every cell/step has a **scope**: `self-<workdir-name>` (`FINOPS_CELL_ID` overrides the name).
A **non-empty explicit scope is the shared-scope override** — that is how knowledge crosses
cells. An empty scope is never global. The retrieval pre-filter is an **exact match**: a
mismatched scope returns ZERO rows (measured 2026-09-21) — zero hits usually mean "wrong
scope", not "empty KB". `acl_scope` defaults to the scope value.

## The read commands

1. **The reader verb** — ranked retrieval, with an automatic fallback to a deterministic scan
   when the services are unreachable:

   ```bash
   agentic-dynamics knowledge read --query "cache hit rate" --scope agentic-dynamics
   agentic-dynamics knowledge read --query "delivery repair" --scope self-mycell --type finding
   agentic-dynamics knowledge read --query "retrieval audit" --contains      # offline scan
   agentic-dynamics knowledge read --query "..." --scope agentic-dynamics --json
   ```

2. **Metadata rows** (no text search — filters only):

   ```bash
   agentic-dynamics registry query --record-type finding --lifecycle current --since 2026-09-20
   agentic-dynamics registry show <knowledge_id>
   agentic-dynamics registry lineage <entity_id>
   ```

3. **Control Room** (read-only HTTP, when the portal runs): `GET /api/registry`,
   `GET /api/registry/<entity_id>`.

## Reader etiquette

- Read `current` lifecycle rows by default; cite `knowledge_id`s exactly.
- Respect authority: `POLICY [P]` > `SOURCE [C]` > `MEASURED [M]` > `DERIVED [C]` >
  `ADVISORY [H]`. A synthesis/contemplation finding is ADVISORY — do not cite it as measured.
- The corpus is dominated by process telemetry (`fact` ~85%, audit 2026-09-21): query with
  distinctive terms; symbol-shaped queries return code symbols, not concepts.
- What we retrieve today: code symbols, process telemetry, spine records
  (decisions/sessions/reflections), and explicitly emitted findings — NOT yet the analysis
  content. The standing audit lives at `docs/reviews/retrieval_audit.md`.

## For phases (in-loop retrieval)

- `rag_augment: true` + `rag_params` retrieves evidence before the first turn of a phase
  (the augmentation seam); `emit_self` defaults ON, and a research phase's report is persisted
  and emitted as a retrievable finding.
- **Emission scope gotcha (measured 2026-09-21):** the metadata finding lands in the phase's
  CELL scope (`self-<workdir>`); the full REPORT record honors `emit_scope` (or the cell scope
  when unset). To retrieve a phase's own findings later, read with the scope it emitted into —
  a reader in another worktree will not see cell-scoped records.
- **Durable emission:** a run executing from an ephemeral worktree should set
  `FINOPS_RESULTS_DIR=<durable-checkout>/experiments/results` so its KB artifacts and reports
  land where their links stay resolvable (the emissions and this reader both honor it).
- A step's own writes are readable by itself: findings emitted into the cell scope are
  retrievable with the same scope (`self-<workdir>`).
