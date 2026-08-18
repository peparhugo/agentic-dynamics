# Canonical-State Architecture — Design Proposal

Design phase of `experiments/specs/canonical_state_design.yaml`. Built on
`docs/canonical_state_inventory.md` (the store map). This is an independent design, not an
implementation — no code in this repo is changed by this document.

## Thesis

**Extend the existing knowledge base rather than build a fourth ledger next to it.**
`src/instrument/knowledge.py`'s `KnowledgeRecord`/`KnowledgeEvent` already carry almost every
primitive a canonical registry needs: a dual sha256 identity (`entity_id` = stable logical
item, `knowledge_id` = one immutable version), an ordinal `Authority`, `valid_from`/`valid_to`,
`observed_at`/`indexed_at`, an `evidence_class`, and — critically — a `KnowledgeEvent.operation`
enum that **already** distinguishes `upsert` / `supersede` / `delete`, with `delete` documented
as "tombstones one" (`knowledge.py:45`). The producer-side ingestion pattern
(`derive_*_records → record_to_artifact → record_to_event → publish_event → stream →
extract_record`) already exists for four `source_type`s (`finding`, `code`, `report`, `policy`)
and is explicitly open-ended (`source_type: str  # code | spec | test | review | report |
episode | policy | ...`).

The inventory phase found no store combining stable identity + full date spine + canonical
status (`docs/canonical_state_inventory.md`, closing paragraph). Rather than reading that as
"build a new thing," this design reads it as "the KB was built with room for this and nothing
walked through the door." **One registry, extended with a `record_type` axis** (open question 1
below is answered "one registry," not three ledgers) — reusing the identity scheme, the
authority ordering, and the event pipeline verbatim, plus two small additive schema changes
(§1) and four new producer modules mirroring the four that already exist (§5).

This also directly serves the "no new transport machinery" convention already stated in
`.claude/rules/conventions.md` ("`compile_experiment.py` generalizes … route new grid/comparison
work through the spec, not through direct calls") — the KB pipeline is exactly the kind of
existing transport this design routes through instead of duplicating.

---

## Open Question 1 — One registry vs three ledgers: fields + identity key

**Decision: one registry.** Three separate ledgers (job/attempt ledger, KB, and a hypothetical
story/review ledger) would mean three joins to answer "what is canonical right now for X" —
directly contradicting the "ONE query" requirement in open question 3. The registry's row type
is `KnowledgeRecord`, and `record_type` is carried by the existing `source_type` field (already
declared open-ended) extended with six new values:

| `source_type` | What it represents | `authority` | `evidence_class` |
|---|---|---|---|
| `story` | one `StoryResult` (existing JSON, pointed at, never copied) | MEASURED | `[M]` |
| `review` | one `CommitReview`/`StoryReview` aggregate | ADVISORY | `[H]` |
| `ledger_job` | one `JobRecord` (materializes `LEDGER_FIELDS`, finally — see §5) | MEASURED | `[M]` |
| `ledger_attempt` | one `AttemptRecord`, including supervisor-monitor sessions (§6b) | MEASURED | `[M]` |
| `observation` | one supervisor verdict (STATUS + WHY), *every* verdict not just flagged ones | ADVISORY | `[H]` |
| `flag` | the human-facing, session-scoped, "newest wins" derivative of `observation` | ADVISORY | `[H]` |

**Schema — two additive fields on `KnowledgeRecord`** (both default `None`, so every one of the
1,913 existing artifact files on disk parses unchanged via `from_dict`'s `.get()` — no rewrite,
per the backward-compatibility priority):

```python
@dataclass(frozen=True)
class KnowledgeRecord:
    # ... all existing fields, unchanged ...

    supersedes: str | None = None
    """The predecessor `knowledge_id` for the same `entity_id`, or None for a first version.
    This is the ONE new pointer the design needs. It is set only on the NEW record — the old
    record's artifact file is never touched (see "why not mutate valid_to on write", OQ2)."""
```

```python
@dataclass(frozen=True)
class KnowledgeEvent:
    # ... all existing fields, unchanged ...

    reason: str = ""
    """Required (non-empty) when operation == "delete" (tombstone) or "supersede" over a
    conflicting version (§ Migration step 5). Optional/empty for a routine first-version
    "upsert". This is what turns a tombstone into something a future session can read without
    spelunking a remediation spec — the WHY travels with the WHAT."""
```

**Identity key — reused verbatim, but `source_uri` is a *logical* locator for event-backed
types, not a filesystem path:**

```
entity_id    = sha256(repository_id | source_uri | logical_locator)     # unchanged formula
knowledge_id = sha256(entity_id | source_revision | content_hash | extractor_version)  # unchanged
```

For `code`/`policy` (existing types), `source_uri` is the file path — correct, because the file
path *is* the stable identity for source code. For the six new types, `source_uri` is a
synthetic, worktree-independent scheme:

| `record_type` | `repository_id` | `source_uri` | `logical_locator` |
|---|---|---|---|
| `story` | `"ai-finops-framework"` (fixed — **not** the worktree path) | `f"story:{story_id}"` | `story_id` |
| `review` | same | `f"review:{story_id}"` | `story_id` |
| `ledger_job` | same | `f"ledger_job:{job_id}"` | `job_id` |
| `ledger_attempt` | same | `f"ledger_attempt:{attempt_id}"` | `attempt_id` |
| `observation` | same | `f"observation:{assessment_id}"` | `assessment_id` (hash of `cell_id`+`at`) |
| `flag` | same | `f"flag_stream:{session_id}"` | `session_id` |

This single choice — hashing a **logical** id (`story_id`, `session_id`, …) instead of a
**physical** path — is what makes stranding structurally impossible going forward (finding 1):
the same `story_id` registered from the main repo or from a worktree at
`/tmp/pipeline/feature_queue-steer-2` computes the *same* `entity_id` regardless of which
checkout did the registering. If the two copies are byte-identical, they collide on
`knowledge_id` too (content-hash is folded in) and the second registration is a free no-op. If
they differ, they become two versions of the same entity — an ordinary supersession, not a
lost file (§ Migration step 5 covers the "which one wins" decision for that case).

One identity formula, two behaviors, no special-casing needed in the function itself — only in
what the producer chooses to hash: `observation`'s `source_uri`/`logical_locator` already
encode per-event uniqueness (`assessment_id`), so the formula naturally produces a
single-version entity (nothing to supersede, an audit-trail record). `story`'s and `flag`'s
encode a *persistent* identity across repeated events (`story_id`, `session_id`), so the same
formula naturally produces a multi-version chain. This uniformity is why one registry, not
three, is the right call — the mechanism doesn't change per type, only the producer's choice of
locator does.

---

## Open Question 2 — Date-spine fields + supersession semantics

Fields, all already on `KnowledgeRecord` except `supersedes` (added above):

- **`observed_at`** — when the underlying fact happened in the real world (a story's
  `completed_at`, a verdict's emission time). This is what a migration backfill preserves even
  when registration happens much later (§ Migration step 4/5): a stranded result registered
  today keeps its *original* `observed_at`, so it sorts correctly among records registered on
  time instead of looking freshly-created.
- **`indexed_at`** — when the registry actually ingested this version. For live data these are
  close together; for backfilled data they can be weeks apart, and that gap is itself useful
  signal ("this was measured in August, registered in October").
- **`valid_from`** — defaults to `observed_at` for a first version; for a superseding version,
  `valid_from` is that version's own `observed_at`/`indexed_at`.
- **`valid_to`** — **computed, not written into the source artifact.** This is a deliberate
  bitemporal choice: the artifact JSON is immutable and write-once (a hard project priority —
  "do not rewrite the existing result JSONs"), so a version's `valid_to` cannot be known at the
  moment it's written (its successor doesn't exist yet). Every produced `KnowledgeRecord`
  therefore always writes `valid_to = null`. The *index* layers (Neo4j node property, the
  manifest's `registry` array, `registry_index.jsonl` — see §4/§5) compute the **effective**
  `valid_to` for any non-current version as its successor's `valid_from`, purely as a derived
  view over the `supersedes` chain. Nothing on disk is ever mutated to "close" a validity window.
- **`supersedes`** — predecessor `knowledge_id`, set only on the new record (never
  back-written onto the old one, same immutability argument).
- **`lifecycle_state`** *(new, index-only — computed, never stored in the artifact, same
  reasoning as `valid_to`)* — one of `current | superseded | tombstoned`. Chosen as a distinct
  name from the existing `JobRecord.status` field (`queued|leased|running|…`) to avoid
  colliding two unrelated "status" concepts once `ledger_job` records live inside the same
  registry.

**Supersession mechanics — reuses `KnowledgeEvent.operation` exactly as already defined:**

- `upsert` — first version of an entity. `supersedes = null`.
- `supersede` — a new `knowledge_id` for an existing `entity_id`; `supersedes` = the prior
  current `knowledge_id` (looked up by the producer immediately before emitting, from the
  index). The consumer flips the predecessor's derived `lifecycle_state` to `superseded` and
  its derived `valid_to` to the new record's `valid_from` — a pure index update, zero writes to
  either artifact file.
- `delete` (**the tombstone**) — used when a record is retracted with **no** replacement under
  the same entity (a contaminated cell that will never be re-measured under that identity — see
  Migration step 6). Requires a non-empty `KnowledgeEvent.reason`. Sets derived
  `lifecycle_state = tombstoned`, `valid_to = event time`. The artifact file is untouched and
  stays on disk forever — "tombstone, not delete" is literal: nothing is ever removed from
  `experiments/results/`.

Two named cross-entity edges (not `supersedes`, which is strictly same-entity) close the two
remaining relationship shapes the design needs, both materialized only in Neo4j (§4):

- **`CLEARED_BY`** — a `flag` tombstoned because a *different* entity (a later `observation`)
  established it's no longer a problem. Used by the automatic flag-clearing logic (§6c).
- **`REPLACED_BY`** — a tombstoned record's fix lives under a genuinely different entity (a
  contaminated story's clean rerun has a different `story_id`, hence a different `entity_id` —
  see Migration step 6). Distinguishes "this got fixed, look over there" from `supersedes`'s
  "this is a newer version of the same thing."

---

## Open Question 3 — The ONE surfacing query/CLI, and the Control Room board

**Not `inventory.py`** (a from-scratch full worktree/DB rescan — a different job; folding
registry queries into it would break its simple "wholesale rebuild" contract). **Not
`monitor.py --json`** (live Redis-only queue telemetry, nothing durable). **Not `retrieve()`**
(the RAG pipeline is built for fuzzy, ranked, prompt-construction retrieval with fusion +
dedup + graph expansion — the wrong shape for "give me the exact current record and its
lineage for this id," which needs a deterministic point lookup, not a ranked candidate list).

**New script: `scripts/registry.py`**, added to the script map alongside `inventory.py` /
`monitor.py` / `generate_manifest.py`:

```
python scripts/registry.py show <id>
    # <id> = story_id | session_id | cell_id | entity_id | knowledge_id-prefix — resolved by
    # trying each interpretation against the index in that order, first match wins, ambiguous
    # matches print all candidates instead of guessing.
    # Prints: record_type, current knowledge_id, lifecycle_state, observed_at, indexed_at,
    # backing file (source_uri), and the full supersede chain oldest -> current with each
    # transition's reason (if any).

python scripts/registry.py query --record-type story --lifecycle tombstoned --since 2026-08-01
    # Filtered listing over the flat index (no Neo4j required).

python scripts/registry.py lineage <entity_id>
    # Just the chain, plus any CLEARED_BY / REPLACED_BY cross-entity edges — requires --live
    # (Neo4j) since cross-entity edges are graph-only, not in the flat index (see §4).
```

Default data source: the manifest's new `registry` array / `registry_index.jsonl` tail (flat
file, zero external dependency — always answerable even if Redis and Neo4j are both down,
mirroring `/api/flags`'s existing file-fallback philosophy). `--live` additionally queries
Neo4j for the two cross-entity edge types. This is the "one query a future session runs" — one
command, one flag to escalate from offline-index to full-graph, explicit about which mode it's
in (never silently guesses).

**Control Room board — `GET /api/registry` and `GET /api/registry/<entity_id>`**, new routes on
`admin/server.py`, styled after the existing `/api/flags` contract (same JSON envelope shape:
`generated_at`, `source`, `degraded`, `warnings`, records array). New UI panel, "Registry" or
"Canonical State," alongside the existing Fleet/Routing/Flags panels:

- A filterable table: `record_type`, `lifecycle_state`, `observed_at`, short `knowledge_id`.
- Selecting a row opens a lineage view: a flat chronological list (oldest → current) of that
  entity's versions, tombstone/supersede reasons shown inline, `CLEARED_BY`/`REPLACED_BY`
  cross-links rendered as "→ see also \<other id\>" rather than a graph visualization (kept
  deliberately simple — see Scope Boundary).
- **Read-only by construction**: both routes are `GET` only, reading the same manifest/Neo4j
  index the CLI reads. Zero new Redis writes, zero calls into `OpenCodeClient`. This satisfies
  the Control Room's existing invariant (`docs/supervisor_design.md` §1: "the supervisor flags;
  the human reviews … Assessment, flag persistence … must never call `send_input` or
  `interrupt`") by simply not adding any capability that could — this board is strictly a new
  window onto data that already exists, exactly like `/api/matrix` and `/api/routing` are today.

---

## Open Question 4 — Store split

| Layer | What lives there | Role |
|---|---|---|
| **Immutable files** | Story JSONs, review JSONs, existing KB artifacts (unchanged); **new** `experiments/results/kb/<knowledge_id>.json` artifacts *only* for record types with no pre-existing file (`ledger_job`, `ledger_attempt`, `observation`, `flag` — `flags.jsonl` itself remains the pointer target for `flag`, so even this is barely a new file, see §6c) | Source of truth for record bodies. Never rewritten. |
| **Neo4j** | `Knowledge` nodes (extended with `supersedes`/derived `lifecycle_state` properties) + new edge types `SUPERSEDES`, `CLEARED_BY`, `REPLACED_BY`, plus the existing `REVIEWS`-style content edges the KB schema already anticipates | The lineage/supersession **graph** — same database as the existing experiment/codebase graph, cleanly separated by label/edge type, no schema conflict |
| **Parquet** (`sessions.parquet`/`stories.parquet`) | Unchanged role — fast local analytics via duckdb. **Gains two join columns**: `entity_id`, `knowledge_id`, stamped by `sync_data.py` calling the same identity helper the producers use | Pure analytic view. Never the source of `lifecycle_state` or lineage — a lab book joins into the registry rather than the registry ever depending on parquet. Rebuildable, as today. |
| **Manifest** (`experiments/data_manifest.json`) | Existing `files{}` block **unchanged** (back-compat) + new `registry: [...]` array — one row per `entity_id` with its current `knowledge_id`, `record_type`, `lifecycle_state`, `observed_at` | **Yes — the manifest becomes the registry's flat-file index.** Regenerated wholesale by an extended `generate_manifest.py`, which now also compacts `registry_index.jsonl` (see §5) into this snapshot array, the same relationship `flags.jsonl` already has to the bounded Redis `supervisor_flags` list: an append-only durable log, and a compacted current-state view derived from it. |

---

## Open Question 5 — KB extension: new record_types through the existing ingestion path

Four new producer modules, mirroring the four that exist (`knowledge_ingestion.py`,
`code_ingestion.py`, `quality_ingestion.py`, `policy_ingestion.py` — same
`EXTRACTOR_VERSION` constant convention, same `derive_*_records()` / `build_*_record()`
function-pair shape):

```
story_ingestion.py       EXTRACTOR_VERSION = "story/v1"
  derive_story_records(story_result: dict, *, repository_id, now=None) -> list[KnowledgeRecord]
  # source_uri points at the EXISTING story JSON file — no copy is written. Reads
  # perturbation_strength / test_executed_success straight off StoryResult (already there).

review_ingestion.py      EXTRACTOR_VERSION = "review/v1"
  derive_review_records(review: dict, *, repository_id, now=None) -> list[KnowledgeRecord]
  # source_uri points at the existing review_{story_id}.json. authority=ADVISORY.

ledger_ingestion.py       EXTRACTOR_VERSION = "ledger/v1"
  derive_ledger_records(story_result, opencode_session_row, summary_entry, *, repository_id,
                        now=None) -> list[KnowledgeRecord]
  # THIS is what finally materializes LEDGER_FIELDS as real rows instead of a schema-only
  # dataclass (inventory finding #22: "schema only — no persisted store exists"). One
  # ledger_job + one-or-more ledger_attempt records per cell, joined by story_id/worktree_name
  # across story JSON (#1), opencode.db (#4), and _results_summary.json (#8). Also produces
  # the supervisor-monitor-session attempt record — see §6b, same function, no bespoke path.

observation_ingestion.py  EXTRACTOR_VERSION = "observation/v1"
  derive_observation_record(verdict, *, repository_id, now=None) -> KnowledgeRecord   # every verdict
  derive_flag_record(flag_jsonl_line, *, repository_id, now=None) -> KnowledgeRecord  # §6c
```

All four flow through the **unchanged** pipeline: `record_to_artifact()` (skipped for
`story`/`review` — the artifact already exists, see above) → `record_to_event()` →
`publish_event()` (the existing `FINOPS_KB_WRITE=1` write guard applies unchanged — no new
write path bypasses it) → stream `kb:v1:changes` → consumer groups.

**One new consumer group**, `kb-registry-v1`, added to `CONSUMER_GROUPS` alongside the existing
`kb-chroma-v1` / `kb-neo4j-v1` / `kb-ledger-v1`. Its handler appends one line to a new
append-only file, `experiments/results/registry_index.jsonl` (deliberately the same pattern as
`flags.jsonl`: durable, append-only, human-greppable, never rewritten), and `generate_manifest.py`
compacts that file's *latest-per-entity* rows into the manifest's `registry` array on every
pipeline run. This gives the CLI/Control Room a real-time-ish (stream-lag-bound, same latency
class as the other three consumer groups today) flat index with zero Neo4j dependency for the
common case, and a durable audit log even if Neo4j is never brought up.

`retrieve()`'s existing per-cell `repository_id` scoping and authority-ordered fusion are
**untouched** — the new record types simply slot into the existing `Authority` ordering
(`MEASURED`/`ADVISORY` as tabulated in §1) and existing scope rules; this design adds no new
ranking or retrieval logic.

---

## Open Question 6 — The supervisor's three output layers as durable records

**(a) The VERDICT → `observation` record, every assessment, not just flagged ones.** Today
`supervise_once()` only calls `emit_flag()` for non-`healthy` verdicts (`scripts/supervise.py`,
`if status not in ("healthy", "unknown")`) — a `healthy` verdict is currently thrown away. This
design registers **every** verdict as an `observation` record (§1: `authority=ADVISORY`,
`evidence_class="[H]"`, per-assessment unique identity — no supersession among observations,
they're independent historical facts, not an evolving belief about one artifact). This closes a
real audit gap: today there is no durable trace that a session was ever assessed *healthy* — a
future session investigating "was anyone watching this cell" gets a silent absence, not a
"yes, healthy at 14:02, 14:03, …" trail.

**(b) The MONITOR SESSION's own cost → an ordinary `ledger_attempt` row, not a bespoke type.**
The monitor is a real flash-model opencode session (`ensure_monitor()` creates it via
`OpenCodeClient.create_session`), so its transcript/tokens/cost already live in `opencode.db`
exactly like any other session — the gap is purely that `inventory.py`/`_results_summary.json`
never scan for it (they walk worktrees and result-file globs, and the monitor session has
neither). `ledger_ingestion.py` (§5) is pointed at the monitor's `session_id` (read from
`monitor_session.json`) the same way it's pointed at any other opencode session row, tagged
`cell_id="supervisor_monitor"` / a synthetic `condition="monitor"` so it sorts distinctly in
cost rollups without inventing a second schema. This is the literal, direct answer to "measured
by the same instrument" — it is the same instrument, same function, same record type.

**(c) The normalized FLAG → durable, session-scoped, supersession-chained.** `flags.jsonl`
(already durable, already has `flag_id` + `at`) becomes the `source_uri` target for `flag`
records — one JSONL line, one registration, no duplicated body (same "point, don't copy"
principle as `story`/`review`). Identity: `entity_id` is stable **per `session_id`**
(`source_uri = f"flag_stream:{session_id}"`), so repeated assessments of the same session form
a `supersedes` chain — this is exactly `/api/flags`' existing "newest wins per `session_id`"
UI rule (`docs/supervisor_design.md` §4), now made durable and queryable instead of computed ad
hoc on every request.

**Clearance ("cleared → tombstoned") is fully automatic, by design — no new mutating route.**
A flag is tombstoned (`delete`, `reason="auto-cleared: subsequent observation was healthy"`,
`CLEARED_BY`-edge to the healthy `observation` that triggered it) the moment a later
`observation` for the same `session_id` reads `healthy`. This requires **zero** new
Control-Room mutation surface: the trigger is a routine `observation` registration (§a), which
the supervisor is already emitting on every poll cycle; a small rule in the `kb-registry-v1`
consumer ("if this observation is healthy and the session has an untombstoned `flag`, emit a
`delete` event for it") is data-plane logic, not a control-plane action, and never touches
`OpenCodeClient`. I deliberately did **not** design a human-facing "clear this flag" button —
see Scope Boundary.

**The flag-only rail is preserved exactly as specified**: nothing added in (a), (b), or (c)
calls `send_input` or `interrupt`. The supervisor's Redis contracts (`supervisor_flags` list,
`supervisor_session_cells` hash) are **unchanged** and remain the live hot-path feeding the
existing Needs-Attention rail — this design adds a durable, queryable *shadow* of that live
state, it does not replace or reroute it. `docs/supervisor_design.md`'s acceptance list (items
1–17) is unaffected because no route or behavior it covers is modified; the new
`/api/registry*` routes are strictly additive and read a different backing store.

---

## Migration plan

Ordered so every step is either read-only-of-source or additive-only, unambiguous cases run
before conflict cases, and the one change touching a currently-running system (the supervisor
loop) lands last.

1. **Schema additions** — add `supersedes` to `KnowledgeRecord`, `reason` to `KnowledgeEvent`,
   document the six new `source_type` values, add `"kb-registry-v1"` to `CONSUMER_GROUPS`. All
   additive with defaults; run the existing KB test suite to confirm the 1,913 existing artifact
   files still parse (they will — missing keys resolve via `.get()` to `None`/`""`).
2. **Build the four producer modules** (§5) + the `kb-registry-v1` consumer handler in
   `kb_worker.py`. Unit-test each against a small fixed sample of real files before any bulk
   run, following the existing `test_retrieval.py` store-double pattern.
3. **Backfill pass 1 — unambiguous canonical records.** Register all 156 main-repo story JSONs,
   their reviews, and all valid `_results_summary.json` entries as `upsert` events,
   `lifecycle_state → current`. Nothing to supersede yet (first pass). Pure read of existing
   sources; only new writes are `registry_index.jsonl` lines and the handful of new-type
   artifact files (`ledger_job`/`ledger_attempt`/`observation`/`flag` records — none of which
   have a pre-existing file to point at instead).
4. **Backfill pass 2 — the un-folded single-task results (finding 3).** Register the
   2026-08-17 task_manager (7 models) + resample results exactly like pass 1. This alone makes
   them canonical and queryable via the registry, **independent of** whether/when
   `analyze_worktrees.py` ever re-runs to fold them into `_results_summary.json` — decoupling
   "is this canonical" from "has the analysis pipeline caught up" is one of the direct payoffs
   of a registry that sits above the derived-view layer.
5. **Backfill pass 3 — the stranded ~59 (finding 1).** Point the story producer at
   `feature/remediation-integrity`'s and `feature/queue-steer-2`'s `experiments/results/stories/`
   directories (both confirmed present locally in the inventory phase — no `git checkout`
   needed, they're worktrees, not deleted branches). Because `entity_id` is worktree-independent
   (§1), a byte-identical duplicate of an already-registered `story_id` is a free no-op
   (`knowledge_id` collides). A genuinely worktree-only file registers as a new `current` record.
   A file whose content *differs* from a same-`story_id` main-repo version is the one case this
   design does **not** auto-resolve: it's surfaced as a named conflict (both candidate
   `knowledge_id`s, both `observed_at`s) for a one-line human call — `supersede` (worktree
   version is the complete/correct one) or `delete` the worktree copy with a reason (main-repo
   version is authoritative). Silent auto-resolution here would just relocate the "recurring
   surprise" this design exists to prevent from "which file is stranded" to "which file silently
   won" — worse, not better.
6. **Tombstone pass — the 77 contaminated cells.** Register each `_remediation_contaminated/`
   file directly as `delete`, `reason` populated from the concrete forensic cause ("P0-7
   mutation fallback ran condition=early_degrade as CLEAN"), `supersedes=null`. If
   `remediation_data_integrity.yaml`'s `rerun_contaminated` phase has already produced a clean
   replacement for the same story/condition (a **different** `story_id`, since it's a genuinely
   new attempt, not a version of the tainted one), register that clean result via pass-1 logic
   as `current` and add a `REPLACED_BY` edge from the tombstoned record to it — this is the
   cross-entity case §2 introduced `REPLACED_BY` for.
7. **Wire the surfaces** — extend `generate_manifest.py` to compact `registry_index.jsonl` into
   the `registry` array; add `scripts/registry.py`; add `/api/registry*` + the Control Room
   panel. Deliberately last among the non-supervisor steps, so these are built and tested
   against the real backfilled corpus from steps 3–6 rather than synthetic fixtures.
8. **Wire the supervisor last.** Extend `supervise_once()`/`emit_flag()` to also call
   `observation_ingestion.py` for every verdict and `ledger_ingestion.py` for the monitor's own
   session. Last because it's the only step touching a live, currently-running loop; landing it
   after the ingestion path is already proven against static backfills (steps 1–7) minimizes the
   blast radius of any mistake to "one more record type," not "the whole registry."

---

## Scope boundary — what this design does NOT build

- **No new mutating Control Room route.** Flag clearance is fully automatic (§6c); there is no
  human "clear this flag" button in this design. Adding one later is a small, isolable follow-on
  if wanted — deferred here to keep the new mutation surface at exactly zero, which is the
  safest possible answer to "does this preserve the flag-only rail."
- **No rewriting or relocation of any existing story/review/result JSON.** Registration is
  pointer-only, everywhere it can be (`story`, `review`, `flag` point at existing files); new
  artifact files are written only for genuinely new record types (`ledger_job`,
  `ledger_attempt`, `observation`).
- **No graph/lineage visualization.** The Control Room's lineage view is a flat chronological
  list with inline reasons, not a rendered graph. A richer visualization is a plausible
  follow-on, not part of this design.
- **No re-scoring, re-analysis, or re-running of contaminated/stale cells.** That is
  `remediation_data_integrity.yaml`'s job. This design only *registers* its outcomes (Migration
  step 6) — it does not duplicate or second-guess that spec's measurement work.
  `analyze_worktrees.py`, `sync_data.py`, and `build_data.py`'s own regeneration logic are
  untouched; the registry sits above them, decoupled (Migration step 4 is the concrete example
  of why that decoupling matters).
- **No changes to `retrieve()`'s ranking, fusion, or scope logic.** New record types slot into
  the existing `Authority` ordering and existing per-cell `repository_id` scoping; no new
  retrieval behavior is introduced.
- **No real-time guarantee.** `kb-registry-v1` is stream-lag-bound like the other three consumer
  groups — "near real time," not instant. A CLI/Control Room read may lag a fresh registration
  by the same margin the KB already tolerates today.
- **No persisted transcript for the monitor session in the registry.** Only its cost/token
  `ledger_attempt` row is registered (§6b) — the full transcript stays in `opencode.db`, which
  remains the transcript store of record for every session, monitor or otherwise; duplicating it
  into the KB would be new, unjustified storage.
- **No unification of the two Neo4j schemas.** The existing experiment/codebase graph (Model,
  ExperimentRun, CodeModule, …) and the new lineage edges (`SUPERSEDES`, `CLEARED_BY`,
  `REPLACED_BY` on `Knowledge` nodes) coexist in the same database by label/edge-type
  separation; no migration of the older schema is proposed or needed.
