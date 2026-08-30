---
status: accepted
---
# CAP Visibility Matrix — who knows what, who can retrieve what

**Status: accepted** — the matrix structure, enforcement trace, and cross-repo isolation rows
are settled. The open decisions (D1–D4, §5) are review items for the addendum d4 review, not
design uncertainty; the matrix is complete without them. Companion to
`context_abstraction_design.md` (the two-channel rule, §6.1 contract-bounded snapshots, §8.6
actuation rail) and the addendum design (I9 patterns, I10 checkpoint). Every cell in the matrix
must trace to an ENFORCEMENT MECHANISM, not a convention — this document's test of completeness
is: *for each "may not" cell, name the machinery that refuses it.*

## 1. Actors and information surfaces

**Actors**

| Actor | Definition |
|---|---|
| Controller | The CAP decision path — `route_next_job_v1` and any future applied rule. Consumes a compiled `ControlContext`. |
| Agent session | An LLM session in a worktree (workflow phase, story session). Can read files and, when RAG is enabled, retrieved knowledge. |
| Reducer | Deterministic machinery — `attempt_facts_v1` … `profiles_v1`, pattern reducer. Produces and consumes facts; never reads narrative. |
| Gate / Compiler | `validate_fact_contracts` (R1–R11) and `compile_context`. Validates requirements and compiles snapshots. |
| Operator | Human — Control Room portal, `registry` CLI, report scripts. |
| Public | The Firebase website + anything published from the public repo. |

**Surfaces**

| Surface | What it is |
|---|---|
| Raw artifacts | Run JSONs, session transcripts, ledgers — the L0 evidence. |
| Knowledge records | Narrative — reviews, findings, stories, policies — the RAG corpus. |
| Facts | Measured/derived/declared rows (the 29 predicates + profiles). |
| Patterns | I9 derived experience: claim, population, conditions, support, uncertainty, validity window, source. |
| Context snapshots | Compiled, contract-bounded `ControlContext`s (I4). |
| Decisions | Shadow proposals (`applied: false`) and (future) applied actuations. |
| Registry lineage | The append-only `registry_index.jsonl` + manifest. |
| Reports | Aggregate measurement output (shadow/decision-arm/context-snapshot reports). |

## 2. The matrix

| Surface | Controller | Agent session | Reducer | Gate/Compiler | Operator | Public |
|---|---|---|---|---|---|---|
| Raw artifacts | — | ✓ own worktree only | ✓ | — | ✓ | ✗ |
| Knowledge records | **✗ never** (C5) | ✓ via RAG (when enabled) | ✗ (produces findings via extractors, never reads) | ✗ | ✓ | selected `[M]` findings only |
| Facts | ✓ **by address only** — the contract's `requires_facts`, nothing more | ❓ **D1** — open | ✓ produce + consume | ✓ validate | ✓ via registry CLI + reports | ✗ |
| Patterns | ✓ consume as facts (derived, `[C]`) | ❓ **D2** — retrieval projection? | ✓ mint (reducer-only, hard rule 3) | ✓ | ✓ via reports | ✗ |
| Context snapshots | ✓ receive compiled | ✗ | ✓ (I4 builders) | ✓ | ✓ | ✗ |
| Decisions | ✓ propose (shadow) / execute (future applied) | ✗ | ✓ record | ✓ validate (C1–C10) | ✓ via reports | ✗ |
| Registry lineage | — | ✗ | ✓ | ✓ | ✓ | ✗ |
| Reports | — | ✗ | — | — | ✓ | ✗ (unpublished) |

## 3. Enforcement trace — every "may not" has a mechanism

| Cell (actor × surface) | Enforcement mechanism |
|---|---|
| Controller × knowledge records | C5 — ADVISORY is structurally uncitable; `is_canonical()` gates consumption; R5 refuses a rule that could consume ADVISORY. |
| Agent × facts (today) | Facts are never written to the retrieval index; `retrieve()` scopes to knowledge records only (two-channel rule). |
| Agent × raw artifacts | Session worktree isolation — a session operates in its own worktree; `cell_scope` scopes KB writes; no lateral reads by address (scope hierarchy). |
| Controller × anything beyond contract | `requires_facts` + `compile_context` — the snapshot contains exactly the contract's facts; `excludes` in the contract; nothing is searched. |
| Decision × actuation | `AUTOMATABLE_ACTIONS = {continue, route}`; fork/compress/escalate are proposal-only; `applied: false` marker; armed gate (`FINOPS_ACTUATION_ARMED`); I7 apply seam OFF by default. |
| Agent × registry lineage | Registry is a CLI/operator surface; agents read knowledge records only. |
| Public × everything except selected findings | Firebase publish path is fed only by the build pipeline from `[M]`/`[C]` findings; provenance checks gate publication. |
| Reducer × narrative | Reducers consume typed `EvidenceItem`/facts; narrative text never enters a reducer input. |

## 4. Cross-repo isolation

The private investing repo (`rrsp-investing`) holds its own fact store, registry, and artifacts
behind `repository_id = rrsp-investing` and private ACL scopes. The public framework repo's
registry, retrieval, reports, and website must never surface them.

| Concern | Enforcement (current) | Gap |
|---|---|---|
| No investing facts in the public registry | Separate repos; `repository_id` scoping on emit | Rows are only separated by repository — an explicit cross-repo visibility POLICY row is missing (a "may not" without machinery beyond repo boundary). |
| No investing knowledge in the public RAG | Separate repos; Chroma/Neo4j instances are per-framework | Same — boundary, not mechanism. |
| No investing records on the website | Website build consumes only framework findings | Same. |

**D3:** decide whether cross-repo isolation is *held by repository boundary alone* (acceptable for
a personal project) or *enforced by ACL machinery* (needed if the framework ever hosts more than
one domain). Recommended: accept the boundary today; record the risk.

## 5. Open decisions (the ❓ cells — for the addendum d4 review)

**D1 — Agent access to facts.** Should agent sessions retrieve facts at all?
- Option A (design status quo): no — agents read knowledge records; facts are for rules.
  Rationale: an agent's job is to act from narrative + measured summaries (reports), not to
  re-derive control truth mid-session.
- Option B: agents may retrieve **patterns** (compressed, uncertainty-carrying, citable) but
  never raw facts — "read what we learned, don't read what is true."
- Option C: full fact retrieval for agents — rejected direction: undermines the two-channel
  rule and invites stale/unsorted fact citation in prompts.
- **Recommendation: B** — a retrieval-facing projection of I9 patterns (a knowledge record
  carrying the PatternPayload) closes the "leverage the entire learned system" gap without
  letting agents consume raw control truth.

**D2 — Pattern projection.** If D1 = B, the projection itself: a knowledge record with
`source_type=pattern`, the PatternPayload as body, authority DERIVED `[C]`, retrievable via the
existing RAG path, and **never** a fact-store row duplication (patterns remain facts; the
projection is a read-only view for agents). Determines: who mints the projection (the pattern
reducer or a separate extractor), idempotency, and staleness coupling to the underlying fact.

**D3 — Cross-repo isolation** (above): boundary vs machinery.

**D4 — Operator fact plane.** The Control Room shows routing/telemetry today, not the fact
plane. Decide the Stage 6 surface: fact coverage view (per predicate), patterns view, and the
shadow-decision viewer. This is display-only — read-only access for the operator, already
granted by the matrix.

## 6. How this document is enforced over time

1. **As policy**: this doc is cited by workflow specs' `domain_context.policies` (the
   visibility rows become declared policy facts once I8 profiles are live).
2. **As tests**: each enforcement row in §3 maps to an existing guard (C5/R5 tests,
   dependency-direction, ACL scope tests). D1/D2 decisions, when made, add their own guards.
3. **As review**: the addendum d4 adversarial review re-checks that no cell drifted from its
   mechanism.

## 7. Sign-off

- [ ] D1 decided (recommend B)
- [ ] D2 designed (pattern projection)
- [ ] D3 accepted (boundary) or escalated (ACL machinery)
- [ ] D4 scheduled (Control Room fact/patterns surface — Stage 6)
- [ ] §3 enforcement trace re-verified against the merged I8–I10 code
