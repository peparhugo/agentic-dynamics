---
status: implemented
implemented_by: feature/canonical-state-r2-fable5
---
# Canonical-State Round 2 — Change-Set

Analyze phase of `experiments/specs/canonical_state_round2.yaml`. This is a diff against
`docs/canonical_state_base_design.md` (the round-1 design), not a rewrite — every entry below
names what changes, why, and which part of the base design (open question, migration step, or
scope boundary) it lands on. Grounding is against the live checkout, not the base design's
prose: where a claim depends on current code behavior, I read the actual file/line rather than
trusting the base inventory's or base verify's characterization of it (both are correct
everywhere I checked, but I re-verified the four gap-relevant sites directly — `story.py:945`,
`supervise.py:221/314/343`, `kb_worker.py:105-134`, `knowledge_stream.py:50/100-120`,
`analyze_worktrees.py:1098`).

Three operator deltas, four base-flagged gaps. Seven entries total; delta 3 gets the deepest
treatment per the round-2 spec's explicit requirement.

---

## Part 1 — Operator deltas

### Delta 1 — Write-time registration (batch backfill demoted to one-time migration)

**What changes.** The base design's Migration plan (steps 3–6) is the *only* place records get
created — `derive_*_records()` walking existing files is presented as the mechanism, full stop.
Round 2 requires flipping that: in steady state, every producer emits its registry record
**inline**, in the same process, immediately after it writes its own artifact — not later, not
via a sweep. The exact call sites, grounded against the live code:

| Producer | Current behavior (confirmed) | Required change |
|---|---|---|
| `src/instrument/story.py:945 save_story_result(result, path)` | `path.write_text(json.dumps(result.to_dict(), indent=2))` — writes JSON, nothing else | After the write succeeds, call `story_ingestion.derive_story_records(result, repository_id=...)` and `publish_event(...)` inline, same call stack, before `save_story_result` returns |
| `scripts/run.py:379` (`path.write_text(json.dumps(out, indent=2, default=str))`) | Single-task result write, zero registry emission | Same pattern — `derive_story_records`-equivalent call inline after the write (this is the exact write path finding-3's "un-folded single-task results" came from; write-time registration means a 2026-08-17-style result is canonical the instant it's written, never dependent on a later fold) |
| Review pipeline (`finalize_reviews.py`, per `review_{story_id}.json` write) | Writes the review JSON only | `review_ingestion.derive_review_records()` inline after write |
| `scripts/supervise.py:221 emit_flag()` and `:314 supervise_once()` | Writes `flags.jsonl` + Redis hot path only; **zero KB emission today** — confirmed by reading both functions directly | `supervise_once()` must call `observation_ingestion.derive_observation_record()` inline for **every** verdict, not gated by the `status not in ("healthy", "unknown")` check at `supervise.py:343` — that check gates *flag* emission (unchanged), not *observation* emission. This is what actually delivers base design OQ6a's "durable healthy trail" promise instead of leaving it as a design description with no call site. |

Batch backfill (`derive_*_records` walking `experiments/results/stories/*.json`,
`_remediation_contaminated/`, the two stranded worktrees) is retained **only** for the base
design's Migration steps 3–6, covering the pre-Delta-1 corpus, explicitly labeled ONE-TIME.
`inventory.py refresh`, `sync_data.py`, and any periodic `reconcile_missing()` pass
(`knowledge_stream.py:55`'s `RECONCILE_INTERVAL_S = 3600`, confirmed) remain reconciliation-only
mechanisms — they may **re-deliver** an event the stream lost, they must never **originate** a
registry record from a filesystem scan once Delta 1 ships.

**Why.** The base verify already diagnosed this exact gap as a residual risk on the one forensic
finding it graded PASS (finding 1, stranding): "nothing in the design walks `git worktree list`
or otherwise proactively finds *future* stranded files... the time-to-discovery for a future
instance of the same write-path bug is not bounded by anything in this design," and recommended
"have `save_story_result()` synchronously emit its own registration event" as a named follow-on
(`canonical_state_base_verify.md:39-42`). Delta 1 promotes that follow-on from optional to
required: a scan only finds what it's pointed at (a worktree path named *after* the fact,
exactly how the original ~59-result stranding evaded detection for as long as it did), so a
design whose steady-state mechanism is still "scan" has not actually closed finding 1 — it has
only made the scan easier to run.

**Affects.** OQ1 (identity formula unchanged — still a logical, not physical, `source_uri` — but
the moment of registration moves from "next backfill run" to "the write"). Migration plan steps
3–6 (downgraded from "the mechanism" to "one-time catch-up for the pre-Delta-1 window"). OQ6a
(verdict registration becomes a mandatory call site, not a design paragraph).

---

### Delta 2 — One typed event stream (explicit invariant, not an implication)

**What changes.** The base design already leans this way in its thesis ("reusing the identity
scheme, the authority ordering, and the event pipeline verbatim") but never states it as a hard
constraint the refine/verify phases must check. Two places in the base design leave room for
drift: OQ4's store-split table still lists four separate storage layers, and OQ5's Migration
step 2 wording — "Build the four producer modules + the `kb-registry-v1` consumer handler" —
can be read as "four ledgers that happen to share a schema" rather than "one ledger with a type
column." Round 2 must state, as a checked invariant:

- Exactly **one** wire format — `KnowledgeEvent` (confirmed fields: `knowledge_id, entity_id,
  operation, source_uri, source_revision, content_hash, occurred_at, schema_version, event_id`
  at `knowledge.py:150-158`), now additionally carrying round-1's `supersedes`/`reason` and
  delta-3's `causes` (below) — for every record type: story, review, ledger_job,
  ledger_attempt, observation, flag, and actuation.
- Exactly **one** stream — `kb:v1:changes` (`STREAM_KEY`, `knowledge_stream.py`) — never a
  per-record-type stream. `CONSUMER_GROUPS` is a flat tuple today (`("kb-chroma-v1",
  "kb-neo4j-v1", "kb-ledger-v1")`, confirmed `knowledge_stream.py:50`) that would *silently*
  permit a type-scoped stream to be bolted on later; round 2 states explicitly that the fourth
  group (round-1's proposed `kb-registry-v1`) subscribes to the same stream as the other three,
  not a new one.
- `source_type` (open-ended string, `knowledge.py:203`) and `operation`
  (`upsert`/`supersede`/`delete`, `knowledge.py:152`) remain the **only** two fields any consumer
  branches on. Nothing else about envelope shape varies per type.

**Why.** This prevents the specific failure mode the operator is naming: round 1's four-producer-
module structure (§5) is easy to implement as "four small new ledgers that share a dataclass"
instead of "one ledger with a type column" — which would recreate the exact fragmentation this
whole effort exists to close, one layer up, *inside* the new system instead of eliminating it.
The base inventory's closing line is the thing this delta is directly answering: "story, review,
ledger, and manifest records are not first-class KB citizens today" — the fix has to be one
citizenship, not four.

**Affects.** OQ1 (record_type lives entirely on `source_type`, never a separate registry table).
OQ4 (files/Neo4j/parquet/manifest are all *derived views* of the one stream — never
independently-written sources of truth for lineage). OQ5 (every producer module converges on one
`publish_event()` call, one stream, one write guard — no per-type shortcut).

---

### Delta 3 — Observation vs actuation

**What changes.** Round 1 has no concept of actuation anywhere — the supervisor is designed as
permanently observe-only, and the base design's Scope Boundary explicitly declines even a
human-facing "clear this flag" *mutation* route, let alone agent-facing control. Round 2 requires
modeling a **future** capability without granting it, using the delta-2 invariant ("`source_type`
+ `operation` are the only discriminators") as the constraint on *how* the two families are
expressed: not a schema fork, not a second envelope — a new `source_type` value plus a
classification function, so the "one stream" guarantee from Delta 2 holds even once actuation
exists as a concept.

**Message families, as a pure function of `source_type` (no new envelope field for the family
itself):**

```python
OBSERVATION_TYPES = {"story", "review", "ledger_job", "ledger_attempt", "observation", "flag"}
ACTUATION_TYPES = {"actuation"}

def message_family(source_type: str) -> str:
    """Classify a record's family from its existing source_type — adds no new field,
    keeps 'source_type + operation are the only discriminators' true after this delta."""
    return "actuation" if source_type in ACTUATION_TYPES else "observation"
```

**Schema — one new `source_type` value, one new envelope field:**

| Field | Value | Grounding |
|---|---|---|
| `source_type` | `"actuation"` (new 7th value alongside round-1's `story/review/ledger_job/ledger_attempt/observation/flag`) | `KnowledgeRecord.source_type` is already documented open-ended (`knowledge.py:203`, `"code \| spec \| test \| review \| report \| episode \| policy \| ..."`) |
| `authority` | `Authority.POLICY` — the existing top ordinal (`Authority` is an `IntEnum` at `knowledge.py:61`; `POLICY` is already used at that tier by `policy_ingestion.py` per the mental-model module map) | Reuses the existing ordering verbatim, per Delta 2 — no new authority tier invented |
| `evidence_class` | `"[P]"` (policy/prior, per the project-wide evidence-class convention in `AGENTS.md`/`conventions.md`) | Actuation is a *decision*, not a measurement — `[P]` is the only class that fits |
| `entity_id` / `source_uri` | `source_uri = f"actuation:{actuation_id}"`, `logical_locator = actuation_id` — a fresh id **per actuation attempt**, not per session (a session may accumulate multiple independent actuation candidates over time; each is its own lineage-linked fact, not a version of a prior one) | Reuses OQ1's logical-locator identity formula verbatim |
| `operation` | `upsert` for a fresh candidate; `delete` with a non-empty `reason` (e.g. `"policy gate declined"`, `"operator vetoed"`) if a candidate is rescinded before it would fire. Never `supersede` — an actuation candidate is not a new version of a prior one, it is an independent decision each time. | Reuses round-1's `operation` enum verbatim, per Delta 2 |
| `causes` | **New envelope field**, third additive field after round-1's `supersedes`/`reason`: `causes: str = ""` on both `KnowledgeEvent` and `KnowledgeRecord`, defaulted (same trailing-default-field placement round-1's verify already validated for `supersedes`/`reason` — appended after existing trailing-default fields, so the 1,913 existing artifacts and round-1's own two additions still parse unchanged) | Cross-entity link (unlike `supersedes`, which is same-entity): the `knowledge_id` of the `observation`-family record that justified this actuation candidate. **Required (non-empty) whenever `source_type == "actuation"`** — enforced by the validator below, not merely documented. |
| Body (`text` field, JSON payload) | `{"actuation_kind": "steer\|interrupt\|escalate\|retry\|budget\|deadline", "target_session_id": ..., "target_cell_id": ..., "requested_action": {...}, "requested_by": "supervisor\|operator\|policy_rule:<name>"}` | No new dataclass field for `actuation_kind` etc. — it lives in the free-text/JSON body exactly the way every other `source_type`'s type-specific payload already does, keeping the envelope itself uniform per Delta 2 |

**Who may emit today vs. future:**

- **Today**: a producer module, `actuation_ingestion.py`, exists with the shape
  `derive_actuation_record(candidate, *, repository_id, now=None) -> KnowledgeRecord` — mirroring
  `observation_ingestion.py`'s function-pair convention exactly — so its schema is exercised by
  unit tests (matching round-1's "test each producer against a fixed sample before any bulk run"
  convention, `tests/test_retrieval.py`'s store-double pattern). It has **zero call sites** in
  `supervise.py`, `workflow_runner.py`, or the Control Room. Nothing in the running system
  constructs an actuation candidate — the shape exists so that enabling it later is an additive
  change (wire one call site + flip one gate), not a schema migration.
- **Future**: a call site is added to `scripts/supervise.py` (or a successor policy-rule
  evaluator) only once a control rule for it exists in a compiled `ExperimentSpec` — the same
  `requires`/`produces` gate `compile_experiment.py` already enforces project-wide for every
  other policy arm (`RuleSpec.plane == "control"`, refused when `requires` are unmet). This is
  the same "measure before policy" ordering `AGENTS.md`'s load-bearing rule already states for
  the rest of the project ("a control rule whose `requires` are not yet measured is unwritable,
  and the compiler refuses it") — actuation gets no bespoke exception to that rule; it becomes
  eligible to fire through the identical mechanism every other policy arm already goes through.

**The `causes` lineage link.** Every actuation record's `causes` is a required, validated
reference to an existing observation-family `knowledge_id`. This makes "why did the system decide
to act" a one-hop lookup — `scripts/registry.py show <actuation_id>` (base design OQ3) follows
`causes` straight to `scripts/registry.py show <observation_id>` — not a log-diving exercise.

**The validator/policy gate that keeps it from firing today.** One gate, enforced in exactly one
place, symmetric with the existing write guard:

- `publish_event()` (`knowledge_stream.py:100-120`) already raises `RuntimeError` unless
  `authorized=True` or `FINOPS_KB_WRITE=1` — confirmed live (`knowledge_stream.py:117-120`). This
  delta adds a **second, independent** check inside the same function: when the event's
  (derived) `message_family == "actuation"`, also require `FINOPS_ACTUATION_ARMED=1` (mirroring
  the existing env-flag pattern exactly) or `armed=True` passed explicitly by the caller —
  default unset/`false`. Both guards must pass to write an actuation event, so turning on
  ordinary KB writes for testing (`FINOPS_KB_WRITE=1`, which every producer already sets today)
  never accidentally arms actuation.
- A second, syntactic check — independent of the arm/disarm flag — rejects any actuation event
  whose `causes` does not resolve to an already-durable observation `knowledge_id` in the index,
  regardless of the arm state. This keeps the *lineage requirement* enforced even in a future
  world where actuation is armed but a caller forgets to populate `causes`.
- Because both checks live inside the single shared `publish_event()` every producer already
  calls (Delta 2's "one stream" guarantee), there is exactly **one** place to audit for "can
  actuation fire today" — not N call sites that could each independently forget the check.
- This gate is a pure allow/deny switch, not a semantic safety validator of *which* actuation is
  wise — that second layer (a real control rule with `requires: [confidence, regret, ...]`) is
  deliberately out of scope for round 2, gated by the same measure-before-policy ordering. Naming
  it here and declining to build it now follows the base design's own Scope Boundary discipline
  (state what you're not building, and why).

**Affects.** OQ1 (`source_type` table gains a 7th row). OQ2 (`causes` joins `supersedes`/`reason`
as envelope additions — same backward-compatible trailing-default placement). OQ6 (the
flag-only rail gets an explicit, gated escape hatch for the future instead of a hard-coded
"never," per the operator's instruction — but the escape hatch arms nothing today: zero call
sites, two independent closed gates). Migration plan needs a new step, distinct from step 8
("wire the supervisor last"): ship `actuation_ingestion.py` and the two `publish_event()` guards,
unit-test the producer against a fixed candidate fixture, and confirm — as an explicit test
assertion, not just a code review — that no call site exists anywhere in `supervise.py` or
`workflow_runner.py`.

---

## Part 2 — Base-flagged gaps (4)

### Gap (a) — Finding 4: `ledger_ingestion` has no fallback for `opencode_session_row is None`

**What changes.** `derive_ledger_records(story_result, opencode_session_row, summary_entry, *,
repository_id, now=None)` keeps its signature but the body branches on
`opencode_session_row is None`: instead of requiring the `opencode.db` join to succeed, it reads
tokens/cost/confidence straight off `story_result["sessions"][i]["agentic"]`. Confirmed live at
`story.py:261-279` — every field the DB join would have supplied is already present there for
*every* backend, opencode or claude_cli, because `StoryResult.agentic` is a plain
`AgenticResult | None` (`story.py:217`) populated the same way regardless of backend:
`prompt_tokens, completion_tokens, reasoning_tokens, answer_tokens, explanation_tokens,
total_tokens, estimated_cost_usd, cache_read_tokens, cache_write_tokens, context_tokens,
confidence`. The resulting `ledger_attempt` record keeps `evidence_class = "[M]"` (this is still
measured, not degraded to heuristic) but is tagged `extractor_version = "ledger/v1-storyfallback"`
— a distinct extractor-version string, the existing project convention for letting a downstream
consumer distinguish two derivations of the same schema without a new field.

**Why.** This is the base verify's only outright **FAIL** among the six forensic findings — the
base design's §5 signature takes `opencode_session_row` as a plain required argument with no
documented `None` branch, so as written the design either crashes or silently mis-joins on every
`claude-fable-5` single-task run, which is the exact symptom of finding 4, just relocated from
`analyze_worktrees.py:1098` into the new ledger producer instead of fixed.

**Affects.** OQ5 (`ledger_ingestion.py`) and OQ6b (the monitor-session cost path reuses the same
function — the fallback branch must also cover the monitor's own session if it, too, ever runs
without a DB row). Migration step 2: the producer's unit test set must include a claude_cli-
backend fixture, not only an opencode-backend one, before any bulk backfill run.

### Gap (b) — Finding 5: `meta_*`/`meta_batch_*` pollution never named or traced

**What changes.** Two parts. First, name the mechanism explicitly in the refined design rather
than relying on an implicit "individually inspectable" argument (the base verify rejected exactly
that as insufficient): registration is per-entity, keyed by logical locator, never by a
title-substring match — so a `meta_*`/`meta_batch_*` session is registered under a distinct
`source_type` (`"meta_session"`, new) rather than folded into `ledger_attempt`, since conflating
meta-analysis session cost with real experiment-attempt cost inside the same bucket would just
relocate today's `analyze_worktrees.py` title-filter pollution into the registry's own rollups
instead of eliminating it — the base design's silence on this point is exactly how it would have
recreated the bug. `ledger_ingestion.py`'s classification step (querying the session title against
`EXPERIMENT_SESSION_PATTERNS`, confirmed imported at `analyze_worktrees.py:32`, the same list the
existing false-positive comes from) runs *before* emission, not after, so a `meta_batch_*` title
is routed to `meta_session` at the point of registration, never mixed into `ledger_attempt` in the
first place. Second, add an explicit Migration step: audit the current 144
`_results_summary.json` entries and `inventory.json`'s `experiment_session_titles` for any
`meta_*`/`meta_batch_*` title that already false-matched the pattern list, and register each
retroactively as a tombstoned `ledger_job`/`ledger_attempt` with `reason="meta-analysis session
misclassified as experiment attempt by title substring match"` (no `REPLACED_BY` — nothing was
lost, this is a pure reclassification, not a remediation).

**Why.** Graded FAIL outright by the base verify: "Finding 5 is never named or traced anywhere in
`docs/canonical_state_design.md`," and the design's only implicit defense — "every registered
entity is individually inspectable... versus today's silent, invisible bias" — was explicitly
rejected as insufficient by the same verify pass ("a plausible implicit mitigation exists... is
not traced to a concrete mechanism, which is what the requirement asks for"). This closes it with
a named `source_type` distinction plus a concrete audit-and-reclassify migration step, matching
the base verify's own recommendation almost verbatim.

**Affects.** OQ1 (new `source_type` value, `meta_session`, alongside the existing six/seven). OQ5
(`ledger_ingestion.py` classifies before emitting, not after). Migration plan: a new audit step
between the base plan's steps 3 and 6.

### Gap (c) — Finding 2: no remediation step for the lost ~83 `_results_summary.json` entries

**What changes.** Add a concrete Migration step — the base verify already specified the exact
mechanism, this just makes it a numbered plan step instead of a recommendation: run `git show
<pre-shrink commit>:experiments/results/_results_summary.json`, diff against the current
144-entry file, and register each of the extra ~83 entries as `upsert` `ledger_job`/`story`
records. `evidence_class` stays `[M]` (they were genuinely measured) but every one of the 83 gets
a mandatory, non-empty `reason` (reusing round-1's `reason` field, its second distinct use beyond
tombstoning — a caveat annotation on an `upsert`, not just a `delete`): `"recovered from git
history <sha>; manifold/semantic labels and cross-matched baselines are known-stale as of the
227→144 shrink."` Cross-check each recovered entry's `story_id`/`cell_key` against the post-shrink
144 and against the pass-1/pass-2 backfilled entries (base plan steps 3–4): any recovered entry
that has since been legitimately re-run under a new `story_id` gets a `REPLACED_BY` edge to that
rerun; every other recovered entry stays a caveated-but-canonical historical record, per the base
verify's own framing — "the source worktree is gone; this is the best available fact, not a
fiction."

**Why.** Graded PARTIAL by the base verify: "the recurrence-prevention half is done... the
remediation-of-past-loss half missing" — and unlike findings 4/5, this is not a judgment call the
operator left open; the base verify already named the exact git command and the exact
disposition logic (register vs. tombstone-via-`REPLACED_BY`). Closing it is transcription into a
plan step, not new design work.

**Affects.** OQ2 (second use of `reason` — caveat-on-upsert, not only tombstone-on-delete).
Migration plan: a new step, placed *after* the pass-1/pass-2 per-entity backfill (needs to check
for rerun-overlap against those first) and *before* pass-6's tombstone pass (some of the 83 may
themselves resolve to a tombstone-with-`REPLACED_BY` once cross-checked).

### Gap (d) — OQ4: the migration plan never extends `kb-neo4j-v1`'s `SET` clause

**What changes.** Extend the Cypher `SET` clause inside `scripts/kb_worker.py`'s `kb-neo4j-v1`
handler. Confirmed by reading the live handler directly (`kb_worker.py:105-134`) rather than
trusting either prior doc's characterization: the current clause sets exactly eleven properties —
`k.entity_id, k.text, k.source_uri, k.authority, k.commit_sha, k.source_type, k.logical_locator,
k.language, k.evidence_class, k.repository_id, k.acl_scope` — and silently drops `valid_from`,
`valid_to`, `observed_at`, `indexed_at`, and (once round 1 ships) `supersedes`. The fix: add four
new bound parameters to the existing `SET` — `k.valid_from = $valid_from, k.observed_at =
$observed_at, k.indexed_at = $indexed_at, k.supersedes = $supersedes` — sourced from
`record.valid_from`, `record.observed_at`, `record.indexed_at`, `record.supersedes`.
`valid_to`/`lifecycle_state` stay **index-only, computed at read time**, exactly as round 1
specified (never written as a stored artifact or graph property — round 1's bitemporal argument
for this was correct; the gap was only that the four *storable* fields were never wired through).
Also add the write path for round 1's own promised `SUPERSEDES` edge, which the base design named
in its OQ4 table but never gave Cypher for either: `MERGE (k)-[:SUPERSEDES]->(prev)` when
`record.supersedes` is non-null and `prev` (looked up by `knowledge_id = record.supersedes`)
exists in the graph.

**Why.** The base verify's own §5 additional check found this precisely: "the design's Migration
plan... never lists 'extend `kb-neo4j-v1`'s Cypher `SET` clause'... without that, OQ4's Neo4j
promise is not achievable by the migration plan as written," graded PARTIAL specifically because
the *design* answer (OQ4's table) was correct but the *plan* omitted the one file-level change
needed to realize it. This is real, not stale — I re-read the handler rather than trusting either
prior doc, and the current `SET` clause names exactly the eleven fields quoted above and nothing
else.

**Affects.** OQ4 (store split, Neo4j layer) and, transitively, Delta 3's `causes` field (once
actuation ships, its cross-entity link needs the same graph-write treatment this gap establishes
for `supersedes` — a `CAUSED_BY` edge is the direct analog, out of scope to build now but the
`SET`-clause fix this gap makes is the prerequisite pattern). Migration plan step 1 or 2: add the
`kb_worker.py` edit plus a graph-adjacent test asserting the four fields and the `SUPERSEDES` edge
round-trip on a live (or fixture) Neo4j instance.

---

## Summary table

| # | Item | Grade in base verify | Core change | Base-design section affected |
|---|---|---|---|---|
| Δ1 | Write-time registration | (residual gap on finding-1 PASS) | Inline emit at 4 call sites; backfill → one-time only | OQ1 identity, Migration steps 3–6, OQ6a |
| Δ2 | One typed event stream | (implicit in thesis, not checked) | Explicit invariant: 1 envelope, 1 stream, 2 discriminator fields | OQ1, OQ4, OQ5 |
| Δ3 | Observation vs. actuation | (absent from round 1 entirely) | New `source_type=actuation`, `causes` field, double-gated `publish_event()` | OQ1, OQ2, OQ6, new Migration step |
| (a) | Finding 4 — no-session fallback | FAIL | Read tokens/cost from `sessions[].agentic` when DB row absent | OQ5, OQ6b, Migration step 2 |
| (b) | Finding 5 — meta_* pollution | FAIL | New `source_type=meta_session`, classify-before-emit, audit migration step | OQ1, OQ5, Migration steps 3–6 |
| (c) | Finding 2 — lost 83 entries | PARTIAL | `git show` recovery step, caveat-on-upsert via `reason` | OQ2, Migration steps 3–6 |
| (d) | OQ4 — Neo4j `SET` clause | PARTIAL | Extend `kb-neo4j-v1` handler + `SUPERSEDES` edge write | OQ4, Migration step 1/2 |
