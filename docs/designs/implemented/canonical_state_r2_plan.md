---
status: implemented
implemented_by: feature/canonical-state-r2-fable5
---
# Canonical-State Round 2 — File-by-File Implementation Plan

Plan phase of `experiments/specs/canonical_state_round2.yaml`. Implements
`docs/canonical_state_round2_design.md` (the refined design) as an ordered list of concrete file
edits. No code is written by this document — every entry names the exact module, function,
constant, or route to add or edit, grounded against the current file (checked directly, not
assumed) so the plan can be executed without re-deriving anything from the design doc.

**Ordering principle:** schema first (additive, zero behavior change) → producers (built,
unit-tested, zero callers) → **ONE-TIME MIGRATION** (backfill the pre-existing corpus, run once,
never re-run) → **STEADY-STATE** (inline emit call sites — the first step touching a live write
path, ordered after migration so it's proven against real backfilled data) → the still-inert
actuation gate → surfacing (built last, against the now-real corpus). This mirrors the design
doc's §12 Migration plan; this document is that plan expressed as file diffs.

Every step below is labeled **[SCHEMA]**, **[PRODUCER]**, **[MIGRATION — ONE-TIME]**,
**[STEADY-STATE]**, **[GATE]**, or **[SURFACE]** so the one-time/steady-state distinction the
requirements call for is never ambiguous at a glance.

---

## Step 1 — [SCHEMA] `src/instrument/knowledge.py`

Add one field to each dataclass (round 1 already added `supersedes`/`reason`; this is round 2's
only schema-layer edit):

```python
# KnowledgeRecord — append after perturbation_strength (the current last field, confirmed
# knowledge.py:227), consistent with round 1's supersedes placement:
causes: str | None = None

# KnowledgeEvent — append after round 1's `reason: str = ""` (confirmed as the current last
# field once round 1 lands):
causes: str = ""
```

Also add, in the same module (co-located with `Authority` since it's a classification over
`source_type`, not a transport concern):

```python
OBSERVATION_TYPES = frozenset({
    "story", "review", "ledger_job", "ledger_attempt",
    "observation", "flag", "meta_session",
})
ACTUATION_TYPES = frozenset({"actuation"})

def message_family(source_type: str) -> str:
    """See docs/canonical_state_round2_design.md §4 for the full rationale."""
    return "actuation" if source_type in ACTUATION_TYPES else "observation"
```

**Verify:** the trailing-default-field placement is checked the same way round 1's verify
checked it — run `python -c "from dataclasses import fields; from instrument.knowledge import
KnowledgeRecord, KnowledgeEvent; print([f.name for f in fields(KnowledgeRecord)])"` and confirm
`causes` is last.

**Test file:** extend `tests/test_knowledge.py` — add assertions for `causes` defaulting to
`None`/`""`, round-tripping through `to_dict()`/`from_dict()`, and existing-artifact
backward-compatibility (a `KnowledgeRecord.from_dict()` call against a fixture dict with no
`causes` key must not raise). Add `test_message_family_classifies_actuation_vs_observation` and
`test_message_family_defaults_unknown_source_type_to_observation` (the "closed allowlist, not
denylist" behavior from design §4 — a made-up `source_type` must classify as `observation`, not
error and not silently become `actuation`).

---

## Step 2 — [PRODUCER] `src/instrument/story_ingestion.py` (new file)

Mirrors `knowledge_ingestion.py`'s module-docstring-first, `EXTRACTOR_VERSION`-constant
convention.

```python
EXTRACTOR_VERSION = "story/v1"
SOURCE_TYPE = "story"

def derive_story_records(
    story_result: dict, *, repository_id: str, now: str | None = None
) -> list["KnowledgeRecord"]:
    """source_uri points at the EXISTING story JSON file — no copy is written."""
```

`build_story_record(story_result, *, repository_id, now=None) -> KnowledgeRecord` (singular,
mirroring `code_ingestion.py`'s `build_code_record` naming) does the actual field construction;
`derive_story_records` is the list-returning wrapper other producers use, for signature symmetry
with `derive_records`/`derive_code_records`/`derive_quality_records`/`derive_policy_records`.

**Export:** add to `src/instrument/__init__.py` — one new import block after the existing
`policy_ingestion` block (confirmed pattern at `__init__.py:246-252`), `"derive_story_records",
"build_story_record"` added to `__all__`.

**Test file (new):** `tests/test_story_ingestion.py`, mirroring `tests/test_knowledge_ingestion.py`'s
structure (imports the module's constants + functions, asserts identity stability across
repeated calls on the same `story_result`, asserts `content_hash` changes when the story JSON's
body changes, asserts `source_uri` is the existing file path — never a new artifact write).

---

## Step 3 — [PRODUCER] `src/instrument/review_ingestion.py` (new file)

```python
EXTRACTOR_VERSION = "review/v1"
SOURCE_TYPE = "review"

def derive_review_records(
    review: dict, *, repository_id: str, now: str | None = None
) -> list["KnowledgeRecord"]:
    """source_uri points at the existing review_{story_id}.json. authority=ADVISORY."""
```

**Export:** same `__init__.py` pattern as step 2.

**Test file (new):** `tests/test_review_ingestion.py`, same structural mirror as step 2's test
file, plus a fixture built from `finalize_reviews.py`'s actual output shape (the merged
`review_{story_id}.json` body, confirmed at `scripts/finalize_reviews.py:64`).

---

## Step 4 — [PRODUCER] `src/instrument/ledger_ingestion.py` (new file — closes gaps a, b)

```python
EXTRACTOR_VERSION = "ledger/v1"
FALLBACK_EXTRACTOR_VERSION = "ledger/v1-storyfallback"   # gap (a)
SOURCE_TYPE_JOB = "ledger_job"
SOURCE_TYPE_ATTEMPT = "ledger_attempt"
SOURCE_TYPE_META = "meta_session"                         # gap (b)

def classify_session(session_title: str) -> str:
    """Returns SOURCE_TYPE_META for meta_*/meta_batch_* titles, else SOURCE_TYPE_ATTEMPT.
    Runs BEFORE emission — see design §7b for why order matters here."""

def derive_ledger_records(
    story_result: dict,
    opencode_session_row: dict | None,
    summary_entry: dict,
    *,
    repository_id: str,
    now: str | None = None,
) -> list["KnowledgeRecord"]:
    """One ledger_job + one-or-more ledger_attempt/meta_session records per cell.
    Branches on opencode_session_row is None (gap a fallback, reads
    story_result['sessions'][i]['agentic']) and on classify_session() (gap b routing) BEFORE
    constructing each attempt record. Also produces the supervisor-monitor-session attempt
    record when pointed at the monitor's own session_id (design §7 / round-1 OQ6b) — same
    function, no bespoke path.
    """
```

Imports `EXPERIMENT_SESSION_PATTERNS` from wherever `scripts/analyze_worktrees.py:32` currently
imports it from (confirmed: a shared constants module — resolve the exact import target when
writing this file; `classify_session` must use the identical list, not a re-declared copy, or
gap (b)'s fix drifts from the thing it's meant to match).

**Export:** `__init__.py`, same pattern — `"derive_ledger_records", "classify_session"`.

**Test file (new):** `tests/test_ledger_ingestion.py`. Required cases, each traced to the gap it
closes:
- `test_derive_ledger_records_uses_db_join_when_session_row_present` — baseline path.
- `test_derive_ledger_records_falls_back_to_agentic_block_when_session_row_none` — **gap (a)**:
  a fixture `story_result` with a populated `sessions[0]["agentic"]` dict (the exact 15-field
  shape at `story.py:261-279`) and `opencode_session_row=None`; assert the emitted record's
  tokens/cost/confidence match the `agentic` block and `extractor_version ==
  "ledger/v1-storyfallback"`.
- `test_classify_session_routes_meta_batch_star_to_meta_session` — **gap (b)**: literal
  regression test for the `meta_batch_*` false-match `docs/canonical_state_base_verify.md`
  documented; assert `classify_session("meta_batch_042")` returns `"meta_session"`, not
  `"ledger_attempt"`.
- `test_classify_session_still_matches_real_experiment_titles` — negative case, guards against
  over-broadening the `meta_*` prefix check.

---

## Step 5 — [PRODUCER] `src/instrument/observation_ingestion.py` (new file)

```python
EXTRACTOR_VERSION = "observation/v1"
SOURCE_TYPE_OBSERVATION = "observation"
SOURCE_TYPE_FLAG = "flag"

def derive_observation_record(
    verdict: dict, *, repository_id: str, now: str | None = None
) -> "KnowledgeRecord":
    """Every verdict, not just flagged ones. authority=ADVISORY, evidence_class=[H]."""

def derive_flag_record(
    flag_jsonl_line: dict, *, repository_id: str, now: str | None = None
) -> "KnowledgeRecord":
    """source_uri points at flags.jsonl (already durable) — no duplicated body."""
```

**Export:** `__init__.py`, same pattern.

**Test file (new):** `tests/test_observation_ingestion.py` — asserts every `status` value
(`healthy`, `stalled`, `off_track`, per `scripts/supervise.py`'s prompt contract at
`supervise.py:51-56`) produces an `observation` record, not only non-`healthy` ones (this is the
literal audit-gap closure round 1's OQ6a described).

---

## Step 6 — [PRODUCER] `src/instrument/actuation_ingestion.py` (new file — Delta 3)

```python
EXTRACTOR_VERSION = "actuation/v1"
SOURCE_TYPE = "actuation"

def derive_actuation_record(
    candidate: dict, *, repository_id: str, now: str | None = None
) -> "KnowledgeRecord":
    """See docs/canonical_state_round2_design.md §5a for the candidate dict shape and §5b
    for who may call this (today: only this file's own unit test)."""
```

**Export:** `__init__.py`, same pattern.

**Test file (new):** `tests/test_actuation_ingestion.py`:
- `test_derive_actuation_record_sets_policy_authority_and_p_evidence_class` — schema shape.
- `test_derive_actuation_record_requires_causes` — raises/rejects a candidate with no
  justifying `causes` id (construction-time check, ahead of the transport-level gate in step 8).
- **`test_no_call_sites_construct_actuation_records`** — the explicit "zero call sites" assertion
  the design calls for (§5b): `grep`-equivalent test, e.g. `ast`-walk or plain substring search
  over `scripts/supervise.py` and `src/instrument/workflow_runner.py` asserting
  `derive_actuation_record` does not appear. This turns "nothing calls this today" from a
  code-review convention into a CI-enforced invariant that fails loudly if a future change
  quietly wires a call site without also flipping the gate in step 8.

---

## Step 7 — [SCHEMA/GATE] `src/instrument/knowledge_stream.py`

Two edits to the existing file:

1. `CONSUMER_GROUPS = ("kb-chroma-v1", "kb-neo4j-v1", "kb-ledger-v1")` (confirmed
   `knowledge_stream.py:50`) → add `"kb-registry-v1"`:
   ```python
   CONSUMER_GROUPS = ("kb-chroma-v1", "kb-neo4j-v1", "kb-ledger-v1", "kb-registry-v1")
   ```

2. `publish_event()` (confirmed `knowledge_stream.py:100-120`) gains one new keyword-only
   parameter and two new guard blocks, inserted immediately after the existing
   `FINOPS_KB_WRITE` check (confirmed at `knowledge_stream.py:117-120`):
   ```python
   def publish_event(
       r: Any,
       event: KnowledgeEvent,
       *,
       stream: str = STREAM_KEY,
       authorized: bool = False,
       armed: bool = False,              # NEW
   ) -> str:
       if not authorized and os.environ.get("FINOPS_KB_WRITE") != "1":
           raise RuntimeError(...)        # unchanged
       if message_family(_source_type_of(event)) == "actuation":   # NEW block
           if not armed and os.environ.get("FINOPS_ACTUATION_ARMED") != "1":
               raise RuntimeError("actuation not armed: ...")
           if not event.causes or not _resolves_to_observation(r, event.causes):
               raise RuntimeError("actuation event missing or invalid `causes`: ...")
       ...  # existing xadd logic unchanged
   ```
   `_source_type_of(event)` — `KnowledgeEvent` itself has no `source_type` field (confirmed
   `knowledge.py:150-158`); it is read from the pointed-at `KnowledgeRecord` at construction
   time via `record_to_event()`. Resolve this either by (a) having `record_to_event()` stash
   `source_type` onto the event as an already-existing pattern would allow, or (b) having
   `publish_event()`'s caller pass `source_type` explicitly alongside `armed`. Pick (b) — it
   keeps `KnowledgeEvent`'s field count exactly as documented in the design (three additive
   fields total: `supersedes`, `reason`, `causes` — no fourth `source_type` field snuck in to
   solve a plumbing problem) and matches how `record_to_event()`'s existing callers already have
   the source `KnowledgeRecord` in scope when they call `publish_event()`.
   `_resolves_to_observation(r, knowledge_id)` — a small helper querying the same index
   `scripts/registry.py show` will read (step 12) for "does this knowledge_id exist and is its
   `source_type` in `OBSERVATION_TYPES`."

**Test file:** extend `tests/test_knowledge_stream.py` — add
`test_publish_event_rejects_actuation_without_armed_flag`,
`test_publish_event_accepts_actuation_when_armed_true_and_causes_valid`,
`test_publish_event_rejects_actuation_with_unresolvable_causes`,
`test_kb_registry_v1_is_a_valid_consumer_group`.

---

## Step 8 — [SCHEMA] `scripts/kb_worker.py` — the `kb-registry-v1` handler + the `kb-neo4j-v1` `SET`-clause fix (gap d)

Two edits to the existing file:

1. **New handler**, added to `build_handler()` (confirmed dispatch structure at
   `kb_worker.py:66-134`, branching on `if group == "kb-ledger-v1"` / `"kb-chroma-v1"` /
   `"kb-neo4j-v1"`):
   ```python
   if group == "kb-registry-v1":
       def handler(record):
           # Append one compacted line to the flat, append-only registry index —
           # deliberately the same durable/human-greppable pattern as flags.jsonl.
           line = {
               "knowledge_id": record.knowledge_id, "entity_id": record.entity_id,
               "source_type": record.source_type, "lifecycle_state": "current",  # computed,
                   # see design §6 — this consumer does not resolve superseded/tombstoned
                   # state; generate_manifest.py's compaction step (step 13) does that by
                   # taking the latest-per-entity_id row from this file
               "observed_at": record.observed_at, "indexed_at": record.indexed_at,
               "supersedes": record.supersedes, "causes": record.causes,
           }
           REGISTRY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
           with open(REGISTRY_INDEX_PATH, "a") as f:
               f.write(json.dumps(line) + "\n")
       return handler
   ```
   `REGISTRY_INDEX_PATH = PROJECT_ROOT / "experiments" / "results" / "registry_index.jsonl"`.

2. **Extend the existing `kb-neo4j-v1` `SET` clause** (confirmed exact current clause at
   `kb_worker.py:118-134`, setting exactly eleven properties and dropping
   `valid_from`/`valid_to`/`observed_at`/`indexed_at`/`supersedes`) per design §6's Cypher block:
   add `k.valid_from`, `k.observed_at`, `k.indexed_at`, `k.supersedes`, `k.causes` to the `SET`,
   plus the `FOREACH ... MERGE (k)-[:SUPERSEDES]->(prev)` block. `valid_to`/`lifecycle_state`
   remain unwritten (computed at read time only — unchanged from round 1's argument).

**Test file (new):** `tests/test_kb_worker.py` — **new file; no existing test covers
`kb_worker.py`'s handlers today** (confirmed by search — zero references to `build_handler` or
`kb_worker` anywhere under `tests/`). Required cases:
- `test_kb_registry_v1_handler_appends_jsonl_line` — asserts the append-only file gets exactly
  one new line per call, with the seven fields listed above.
- `test_kb_neo4j_v1_handler_sets_date_spine_fields` — **gap (d)** regression test: constructs a
  fake Neo4j client double (mirroring `tests/test_retrieval.py`'s store-double pattern — a
  minimal object recording the Cypher params it was called with, not a live Neo4j connection),
  asserts the `SET` clause's bound-parameter dict includes `valid_from`, `observed_at`,
  `indexed_at`, `supersedes`, `causes` — the exact fields the base inventory proved were silently
  dropped.
- `test_kb_neo4j_v1_handler_writes_supersedes_edge_when_present` — asserts the `MERGE
  (k)-[:SUPERSEDES]->(prev)` Cypher fires only when `record.supersedes` is non-null.

---

## Step 9 — [MIGRATION — ONE-TIME] `scripts/kb_produce_registry.py` (new file)

Mirrors `scripts/kb_produce_sources.py`'s exact shape (confirmed structure: a `_SOURCES` dict of
`{key: (source_type_label, derive_fn)}`, an `argparse` CLI selecting one or more keys, a
`--dry-run` flag) rather than inventing a new CLI pattern:

```python
_SOURCES = {
    "story": ("story", derive_story_pass1),          # main-repo 156 story JSONs
    "story-worktree": ("story", derive_story_pass3),  # stranded ~59 — finding 1
    "review": ("review", derive_review_pass1),
    "summary-recovery": ("story", derive_summary_recovery_pass),  # lost ~83 — gap (c)
    "contaminated": ("story", derive_contaminated_tombstone_pass),  # 77 cells, delete+reason
    "meta-audit": ("meta_session", derive_meta_audit_pass),         # gap (b) retro-tag
}
```

Each `derive_*_pass` function is a thin wrapper that reads the relevant existing files (main
repo or, for `story-worktree`, the two worktree paths named in the design:
`/tmp/pipeline/feature_remediation-integrity`, `/tmp/pipeline/feature_queue-steer-2`) and calls
the step-2/3/4 producer functions — no new derivation logic lives in this file, it is purely an
orchestration/CLI layer, exactly like `kb_produce_sources.py` is for the four existing batch
source types.

**Run order (this is the "ONE-TIME MIGRATION" sequence — executed once, by an operator, never
by a cron or a steady-state code path):**

```
python scripts/kb_produce_registry.py --source story          # pass 1: 156 main-repo stories
python scripts/kb_produce_registry.py --source review          # pass 1: reviews
python scripts/kb_produce_registry.py --source story-worktree   # pass 3: stranded ~59
python scripts/kb_produce_registry.py --source summary-recovery # pass 3: lost ~83, gap (c)
python scripts/kb_produce_registry.py --source contaminated     # pass 6: 77 tombstones
python scripts/kb_produce_registry.py --source meta-audit       # pass 6: gap (b) retro-tag
```

Each invocation sets `FINOPS_KB_WRITE=1` for its own process only (matching
`kb_produce_sources.py`'s existing convention, confirmed in `knowledge_stream.py`'s
`publish_event` docstring: "`scripts/kb_produce.py` (and `scripts/kb_produce_sources.py`) set the
env flag for their whole run"). **None of these six invocations ever sets
`FINOPS_ACTUATION_ARMED`** — this script only ever emits `story`/`review`/`meta_session` records,
never `actuation`, so the step-7 gate is never exercised by migration at all.

**Test file (new):** `tests/test_kb_produce_registry.py`, mirroring whatever store-double /
dry-run-smoke pattern `tests/test_knowledge_ingestion.py`'s batch-producer tests already use for
`kb_produce.py` — one test per `_SOURCES` key asserting the right `derive_*` function is called
and the right `source_type` label is attached, plus a `--dry-run` smoke test that touches no
Redis/filesystem state.

---

## Step 10 — [STEADY-STATE] `src/instrument/story.py`

Edit `save_story_result(result: StoryResult, path: Path) -> None` (confirmed exact current body
at `story.py:945-948`: `path.parent.mkdir(...)`; `path.write_text(json.dumps(...))`; nothing
else). Add, after the write succeeds, in the same function:

```python
def save_story_result(result: StoryResult, path: Path) -> None:
    """Save a StoryResult as JSON, then register it inline (write-time registration —
    Delta 1: this call site is why finding-1-style stranding cannot recur; a scan would only
    find this file if pointed at the right worktree, but this line always fires)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2))

    if os.environ.get("FINOPS_KB_WRITE") == "1":   # opt-in, same convention as every existing
                                                      # KB writer — a plain `save_story_result`
                                                      # call in a test or a read-only tool never
                                                      # accidentally emits
        from .story_ingestion import derive_story_records
        from .knowledge_stream import connect, publish_event
        r = connect()
        for record in derive_story_records(result, repository_id=REPOSITORY_ID):
            publish_event(r, record_to_event(record), authorized=True)
```

**Why gated on `FINOPS_KB_WRITE` here too, not unconditional:** keeps `save_story_result()` safe
to call from any test or tool without accidentally requiring live Redis — matches the existing
project-wide convention rather than inventing a new one for this call site specifically.

**Test file:** extend `tests/test_story.py` (the existing 330-line file per `conventions.md`) —
add `test_save_story_result_emits_registry_event_when_kb_write_enabled` and
`test_save_story_result_skips_emission_when_kb_write_unset` (using a store-double Redis, not a
live connection).

---

## Step 11 — [STEADY-STATE] `scripts/run.py`

Edit `_save_results(runs, name, model_label, results_dir)` (confirmed exact current body at
`run.py:373-381`: builds `out` dict, `path.write_text(json.dumps(out, indent=2, default=str))`,
prints). Same pattern as step 10 — after the write, gated on `FINOPS_KB_WRITE`, call
`story_ingestion.derive_story_records`-equivalent emission for the single-task result shape
(`out`'s `experiment`/`model`/`runs` structure, not a full `StoryResult` — `story_ingestion.py`'s
`build_story_record` needs a second entry point or a light adapter for this shape; resolve by
adding `derive_story_records_from_run_output(out, *, repository_id, now=None)` to
`story_ingestion.py` in step 2 rather than duplicating identity-formula logic here).

**Test file:** extend `tests/test_pipeline.py` or add a targeted test in
`tests/test_story_ingestion.py` (step 2) for the run.py-shaped adapter specifically, whichever
existing file already covers `_save_results`' output shape — check at implementation time and
extend in place rather than creating a redundant third test file for the same producer.

---

## Step 12 — [STEADY-STATE] `scripts/finalize_reviews.py`

Edit `_finalize_story(story_id)` (confirmed exact write site at `finalize_reviews.py:64`:
`(REVIEWS_DIR / f"review_{story_id}.json").write_text(json.dumps(data, indent=2))`). Same
gated-emit pattern as steps 10–11, calling `review_ingestion.derive_review_records(data,
repository_id=...)` immediately after the write.

**Test file:** extend whichever test currently covers `finalize_reviews.py` (check at
implementation time — none was found in this plan's file survey; if none exists, add
`tests/test_finalize_reviews.py` new, covering both the merge logic already there and the new
emission call).

---

## Step 13 — [STEADY-STATE] `scripts/supervise.py`

Edit `supervise_once(client, monitor_id, redis_client)` (confirmed exact current body at
`supervise.py:314-344`: reads cell activity, computes `status`/`why`, then `if status not in
("healthy", "unknown"): emit_flag(...)`). Add, **before** that conditional (so it runs for every
verdict, not only flagged ones — this is the literal fix for round 1's OQ6a audit gap):

```python
for cell_id in cells:
    ...
    status, why = ...   # unchanged assessment logic

    # NEW — Delta 1 + round-1 OQ6a: register EVERY verdict, unconditionally.
    if os.environ.get("FINOPS_KB_WRITE") == "1":
        from instrument.observation_ingestion import derive_observation_record
        record = derive_observation_record(
            {"cell_id": cell_id, "status": status, "why": why, "model": model},
            repository_id=REPOSITORY_ID,
        )
        publish_event(redis_client, record_to_event(record), authorized=True)

    if status not in ("healthy", "unknown"):     # UNCHANGED — still gates flag emission only
        emit_flag({"id": cell_id, "title": cell_id, "model": {"id": model}}, status, why)
```

Also edit `emit_flag()` (confirmed `supervise.py:221-236`) to call
`observation_ingestion.derive_flag_record()` inline after its existing
`flags.jsonl` append + Redis push, same `FINOPS_KB_WRITE`-gated pattern.

**This is the one step in the steady-state group that touches a currently-live, running loop** —
ordered last among steady-state wiring per the design's migration-plan rationale (§12 step 7):
land it only after steps 2–9 have already proven the producer modules against static backfills.

**Test file:** extend `tests/test_supervise.py` (confirmed existing, 2 tests today at
`test_supervise.py:31,53`) — add `test_supervise_once_registers_every_verdict_including_healthy`
(the literal OQ6a assertion — a `healthy` verdict must produce an `observation` record even
though it produces no flag) and `test_emit_flag_also_registers_flag_record`.

---

## Step 14 — [GATE] verify the actuation gate stays inert (no file edit — a standing test assertion)

No production file changes in this step. This step **is** step 6's
`test_no_call_sites_construct_actuation_records` test plus a second, repo-wide assertion added to
`tests/test_knowledge_stream.py`: `test_finops_actuation_armed_is_unset_by_default` — asserts
`os.environ.get("FINOPS_ACTUATION_ARMED")` is not `"1"` in the default test environment
(guards against a future `.env`/CI config change silently arming actuation without anyone
noticing, since nothing else in the test suite would catch that).

---

## Step 15 — [SURFACE] `scripts/generate_manifest.py`

Edit `main()` (confirmed exact current structure: builds `manifest` dict with `files: {}`
populated from a fixed `files_to_hash` dict, confirmed `generate_manifest.py:37-59`). Add, after
the existing `files_to_hash` loop:

```python
manifest["registry"] = _compact_registry_index(REGISTRY_INDEX_PATH)
# _compact_registry_index: read experiments/results/registry_index.jsonl (written by step 8's
# kb-registry-v1 handler), keep only the latest-by-indexed_at row per entity_id, return as a
# list — the same "append-only log + compacted snapshot" relationship flags.jsonl already has
# to its own Redis mirror.
```

`manifest["files"]` block is otherwise byte-for-byte unchanged — backward compatibility
requirement from the design (§11).

**Test file:** extend whichever test covers `generate_manifest.py` today (check at
implementation time) or add `tests/test_generate_manifest.py` new if none exists, asserting the
`registry` array reflects only the newest row per `entity_id` from a multi-version fixture
JSONL.

---

## Step 16 — [SURFACE] `scripts/registry.py` (new file)

```
python scripts/registry.py show <id>
    # id = story_id | session_id | cell_id | entity_id | knowledge_id-prefix — tried in that
    # order, first match wins, ambiguous prints all candidates. For an actuation record,
    # additionally follows `causes` and prints the justifying observation inline (design §10).

python scripts/registry.py query --record-type {story|review|ledger_job|ledger_attempt|
    observation|flag|meta_session|actuation} --lifecycle {current|superseded|tombstoned}
    --since <date>
    # Filtered listing over experiments/data_manifest.json's registry array (step 15's output) —
    # zero external dependency, matches /api/flags' existing file-fallback philosophy.

python scripts/registry.py lineage <entity_id>
    # supersedes chain + CLEARED_BY/REPLACED_BY cross-entity edges — requires --live (Neo4j).
```

**Test file (new):** `tests/test_registry_cli.py` — one test per subcommand against a fixture
manifest, plus `test_show_actuation_follows_causes_to_observation` (the one behavior specific to
round 2).

---

## Step 17 — [SURFACE] `admin/server.py`

Add two routes, styled after the existing `@app.get("/api/flags")` (confirmed exact decorator
convention at `admin/server.py:848-857`):

```python
@app.get("/api/registry")
def api_registry() -> Response:
    """Filterable table over the manifest's registry array — GET only, read-only by
    construction (same invariant as /api/flags and /api/matrix — no send_input/interrupt
    anywhere in this file, unchanged by this design)."""

@app.get("/api/registry/<entity_id>")
def api_registry_lineage(entity_id) -> Response:
    """Lineage view for one entity: supersede chain + causes (for actuation records)."""
```

New Control Room UI panel ("Registry" / "Canonical State"), alongside the existing Fleet/
Routing/Flags panels — filterable table + lineage view per design §10.

**Test file:** extend `tests/test_admin_server.py` (confirmed existing `FakeRedis`/`FakePubSub`
double pattern at `test_admin_server.py:10-126` — reuse those doubles rather than inventing new
ones), adding `test_api_registry_returns_filtered_table` and
`test_api_registry_lineage_renders_causes_for_actuation_records`, mirroring the file's existing
`test_matrix_*`/`test_queue_reinterleave_*` naming and structure.

---

## Verification gate — pytest modules that must pass before this change ships

Run in this order (schema → producers → transport/gate → migration → steady-state → surface),
matching the file-edit order above so a failure localizes to the right layer:

```
pytest tests/test_knowledge.py -v                     # step 1 — schema + message_family
pytest tests/test_story_ingestion.py -v                # step 2 (new)
pytest tests/test_review_ingestion.py -v               # step 3 (new)
pytest tests/test_ledger_ingestion.py -v               # step 4 (new) — gaps a, b
pytest tests/test_observation_ingestion.py -v          # step 5 (new)
pytest tests/test_actuation_ingestion.py -v             # step 6 (new) — Delta 3, incl. the
                                                          #   zero-call-sites assertion
pytest tests/test_knowledge_stream.py -v                # step 7 — the two publish_event gates
pytest tests/test_kb_worker.py -v                       # step 8 (new) — gap (d) regression
pytest tests/test_kb_produce_registry.py -v              # step 9 (new) — migration driver
pytest tests/test_story.py -v                            # step 10 — inline emit
pytest tests/test_pipeline.py -v                          # step 11 — inline emit (run.py)
pytest tests/test_finalize_reviews.py -v                  # step 12 — inline emit (reviews)
pytest tests/test_supervise.py -v                          # step 13 — inline emit + OQ6a
pytest tests/test_admin_server.py -v                       # step 17 — /api/registry*
pytest tests/test_registry_cli.py -v                        # step 16 — CLI
pytest tests/test_knowledge_ingestion.py tests/test_code_ingestion.py \
       tests/test_quality_ingestion.py tests/test_policy_ingestion.py \
       tests/test_knowledge_isolation.py -v                 # full regression: the 4 existing
                                                              # producers + isolation guarantees
                                                              # must be untouched by this change
pytest tests/ -v                                             # full suite, final gate — the
                                                              # 1,913-artifact backward-compat
                                                              # check runs implicitly through
                                                              # every existing KB test's fixtures
```

**Hard requirement before merge:** `test_no_call_sites_construct_actuation_records` (step 6) and
`test_finops_actuation_armed_is_unset_by_default` (step 14) must both be green — these are the
two tests that make "actuation cannot fire today" a CI-enforced fact rather than a design-doc
claim. A red result on either blocks the merge unconditionally, independent of every other test
in the suite.
