# Canonical-State Architecture — Round 2, Implementation-Ready Design

Refine phase of `experiments/specs/canonical_state_round2.yaml`. This document supersedes
`docs/canonical_state_base_design.md` by incorporating every item in
`docs/canonical_state_round2_changes.md` (the change-set): three operator deltas (write-time
registration, one typed event stream, observation-vs-actuation) and four base-flagged gaps
(Finding 4 no-session, Finding 5 meta_* pollution, Finding 2 lost-83 remediation, OQ4 Neo4j
`SET`-clause completeness). Everything here is schema-level and file/line-grounded, not prose —
the file-by-file implementation plan is a separate deliverable (`docs/canonical_state_round2_plan.md`,
the next phase). No code in this repo is changed by this document.

---

## 1. The envelope — one dataclass pair, three additive fields total

Round 1 added two fields (`supersedes`, `reason`). Round 2 adds one more (`causes`), all
trailing-default, all backward-compatible by the same argument round 1's own verify already
validated: Python dataclass field ordering only allows a new defaulted field *after* the existing
trailing-default fields, so every one of the 1,913 existing `experiments/results/kb/*.json`
artifacts continues to parse unchanged via `from_dict()`'s `.get()`-based construction — missing
keys resolve to `None`/`""`, never a `TypeError`.

```python
@dataclass(frozen=True)
class KnowledgeRecord:
    # --- existing fields, byte-for-byte unchanged (knowledge.py:191-227) ---
    knowledge_id: str
    entity_id: str
    source_uri: str
    source_type: str            # open-ended; round 2 adds 3 new values — see §2
    logical_locator: str
    repository_id: str
    branch: str
    worktree_id: str
    commit_sha: str
    content_hash: str
    extractor_version: str
    embedding_version: str
    authority: "Authority"      # unchanged IntEnum ordering: POLICY > SOURCE > MEASURED > DERIVED > ADVISORY
    valid_from: str
    valid_to: str | None
    observed_at: str
    indexed_at: str
    acl_scope: str
    contains_sensitive_data: bool
    text: str
    token_count: int
    language: str
    symbols: list[str]
    outcome_id: str
    test_executed_success: bool | None
    evidence_class: str         # [M] [C] [H] [P] [X]
    confidence: float | None = None
    perturbation_strength: float | None = None

    # --- round 1 additions (unchanged) ---
    supersedes: str | None = None
    """Predecessor knowledge_id for the SAME entity_id. Same-entity chain only."""

    # --- round 2 addition ---
    causes: str | None = None
    """The knowledge_id of the OBSERVATION-family record that justified this record's
    existence. Cross-entity (unlike supersedes). Populated ONLY on source_type == "actuation"
    records today; None everywhere else. Required (validator-enforced, see §5) whenever
    source_type == "actuation" — an actuation record with no causes is rejected before it
    reaches the stream, not merely discouraged by convention.
    """
```

```python
@dataclass(frozen=True)
class KnowledgeEvent:
    # --- existing fields, byte-for-byte unchanged (knowledge.py:150-158) ---
    knowledge_id: str
    entity_id: str
    operation: str               # upsert | supersede | delete — unchanged enum, see §6
    source_uri: str
    source_revision: str
    content_hash: str
    occurred_at: str
    schema_version: str
    event_id: str = ""

    # --- round 1 addition (unchanged) ---
    reason: str = ""
    """Non-empty when operation == "delete" (tombstone) or "supersede" over a conflicting
    version, OR (round 2 addition to its usage, not its shape) as a caveat annotation on an
    "upsert" for a record recovered from git history with known-stale provenance (gap c, §7c).
    """

    # --- round 2 addition ---
    causes: str = ""
    """Mirrors KnowledgeRecord.causes onto the event envelope itself, so a consumer can reject
    a malformed actuation event (§5's validator) without first materializing the record.
    """
```

**Invariant this section establishes (Delta 2):** these two dataclasses, unchanged in field
*count-that-matters* (three additive, defaulted fields across two rounds), are the **only**
message shape in the system. Every record type below — including the two new families
introduced by round 2 — is an instance of `KnowledgeRecord`/`KnowledgeEvent`, discriminated
solely by `source_type` + `operation`. There is no second dataclass, no parallel ledger schema,
no per-type envelope variant anywhere in this design.

---

## 2. `source_type` table — 9 values total (6 from round 1, 3 new)

| `source_type` | Introduced | `authority` | `evidence_class` | `message_family` (§4) | What it represents |
|---|---|---|---|---|---|
| `story` | round 1 | MEASURED | `[M]` | observation | One `StoryResult`, pointer-only |
| `review` | round 1 | ADVISORY | `[H]` | observation | One `CommitReview`/`StoryReview`, pointer-only |
| `ledger_job` | round 1 | MEASURED | `[M]` | observation | One `JobRecord`, materializes `LEDGER_FIELDS` |
| `ledger_attempt` | round 1 | MEASURED | `[M]` | observation | One `AttemptRecord`, incl. supervisor-monitor sessions |
| `observation` | round 1 | ADVISORY | `[H]` | observation | One supervisor verdict, *every* verdict |
| `flag` | round 1 | ADVISORY | `[H]` | observation | Session-scoped "newest wins" derivative of `observation` |
| `meta_session` | **round 2 — gap (b)** | ADVISORY | `[H]` | observation | A `meta_*`/`meta_batch_*` analysis session — kept OUT of `ledger_attempt` rollups by construction |
| `actuation` | **round 2 — Δ3** | POLICY | `[P]` | actuation | A steer/interrupt/escalate/retry/budget/deadline candidate — not authorized to fire today |

No tenth value is anticipated by this design; adding one later is additive (a new row in this
table, a new producer module, zero change to the envelope or the stream).

---

## 3. Identity formulas — unchanged mechanism, extended table

```
entity_id    = sha256(repository_id | source_uri | logical_locator)     # unchanged, round 1
knowledge_id = sha256(entity_id | source_revision | content_hash | extractor_version)  # unchanged
```

| `source_type` | `repository_id` | `source_uri` | `logical_locator` |
|---|---|---|---|
| `story` | `"ai-finops-framework"` (fixed, not the worktree path) | `f"story:{story_id}"` | `story_id` |
| `review` | same | `f"review:{story_id}"` | `story_id` |
| `ledger_job` | same | `f"ledger_job:{job_id}"` | `job_id` |
| `ledger_attempt` | same | `f"ledger_attempt:{attempt_id}"` | `attempt_id` |
| `observation` | same | `f"observation:{assessment_id}"` | `assessment_id` (hash of `cell_id`+`at`) |
| `flag` | same | `f"flag_stream:{session_id}"` | `session_id` |
| `meta_session` | same | `f"meta_session:{session_id}"` | `session_id` |
| `actuation` | same | `f"actuation:{actuation_id}"` | `actuation_id` (hash of `target_session_id`+`observation_knowledge_id`+`occurred_at`) — **one identity per candidate, not per session**: repeated actuation candidates against the same session are independent facts, never versions of each other |

Worktree-independence (the mechanism that makes finding-1-style stranding structurally
impossible) is unchanged: every `source_uri` above hashes a **logical** id, never a filesystem
path.

---

## 4. Message family — a pure function, not a new field

Delta 2 requires that `source_type` + `operation` remain the only discriminators a consumer
needs. Observation-vs-actuation (Delta 3) is therefore expressed as a *classification*, not a
schema fork:

```python
OBSERVATION_TYPES = frozenset({
    "story", "review", "ledger_job", "ledger_attempt",
    "observation", "flag", "meta_session",
})
ACTUATION_TYPES = frozenset({"actuation"})

def message_family(source_type: str) -> str:
    """Classify a record's family from source_type alone. Adds no envelope field —
    the whole point is that 'source_type + operation are the only discriminators'
    stays true after this design lands, not just before it.
    """
    if source_type in ACTUATION_TYPES:
        return "actuation"
    return "observation"        # includes any future source_type by default — actuation
                                 # membership is an explicit opt-in allowlist, never inferred
```

`ACTUATION_TYPES` is deliberately a single-member allowlist, not a denylist over
`OBSERVATION_TYPES`: a brand-new `source_type` added in the future defaults to `observation`
(the safe family) unless someone explicitly adds it to `ACTUATION_TYPES` and threads it through
the gate in §5. This is the same "closed by default" posture as the gate itself.

---

## 5. Observation vs. actuation — the concrete envelope, authority, and gate (Delta 3)

### 5a. Schema recap (see §1/§2 for the field definitions)

- `source_type = "actuation"`, `authority = Authority.POLICY`, `evidence_class = "[P]"`.
- `causes` (required, non-empty, validator-enforced): the `knowledge_id` of the
  `observation`-family record that justified this candidate.
- `operation`: `upsert` for a fresh candidate. `delete` (with non-empty `reason`) if a candidate
  is rescinded before it fires. Never `supersede` — see §3, one identity per candidate.
- Body (`text`, JSON payload — no new dataclass field, keeps the envelope uniform):

```python
{
    "actuation_kind": "steer | interrupt | escalate | retry | budget | deadline",
    "target_session_id": str,
    "target_cell_id": str,
    "requested_action": {...},          # kind-specific payload, opaque to the envelope
    "requested_by": "supervisor | operator | policy_rule:<rule_name>",
}
```

### 5b. Who may construct a record — today vs. future

```python
# actuation_ingestion.py — EXTRACTOR_VERSION = "actuation/v1"
def derive_actuation_record(
    candidate: dict, *, repository_id: str, now: str | None = None
) -> KnowledgeRecord:
    """Builds an actuation KnowledgeRecord from a candidate dict (§5a's body shape).

    This function EXISTS and is unit-tested (a fixed candidate fixture, mirroring
    tests/test_retrieval.py's store-double pattern) so its schema is exercised before
    anything ever calls it in the running system. It has ZERO call sites in
    scripts/supervise.py, src/instrument/workflow_runner.py, or admin/server.py as of this
    design — that absence is itself part of the design and is asserted by a dedicated test
    (§ plan phase: "grep-for-zero-call-sites" test), not merely a code-review convention.
    """
```

**Today:** nobody. The function is reachable only from its own unit test.

**Future:** a call site is added to `scripts/supervise.py` (or a successor policy-rule
evaluator) *only* once a control rule for actuation exists in a compiled `ExperimentSpec` —
the same `requires`/`produces` gate `compile_experiment.py` already enforces for every other
policy arm (`RuleSpec.plane == "control"`, refused when `requires` are unmet). This is
`AGENTS.md`'s project-wide load-bearing rule ("a control rule whose `requires` are not yet
measured is unwritable, and the compiler refuses it") applied to actuation with **no bespoke
exception** — actuation becomes eligible to fire through the identical mechanism every other
policy arm already goes through, not a supervisor-only side door.

### 5c. The gate — two independent, closed-by-default checks inside `publish_event()`

```python
def publish_event(
    r: Any,
    event: "KnowledgeEvent",
    *,
    stream: str = STREAM_KEY,
    authorized: bool = False,
    armed: bool = False,          # NEW — round 2. Independent of `authorized`.
) -> str:
    """Append a pointer event to the change stream; return its entry id.

    WRITE GUARD (round 1, unchanged): raises RuntimeError unless authorized=True or
    FINOPS_KB_WRITE == "1". Applies to every event regardless of family.

    ACTUATION GATE (round 2, NEW): when message_family(event's derived source_type) ==
    "actuation", ALSO requires armed=True or FINOPS_ACTUATION_ARMED == "1" — checked
    in addition to, not instead of, the write guard above. Default unset/false. This means
    FINOPS_KB_WRITE=1 (which every existing producer already sets for its whole run) never
    accidentally arms actuation — the two flags are orthogonal on purpose.

    LINEAGE GATE (round 2, NEW): when source_type == "actuation", `event.causes` must be a
    non-empty knowledge_id that resolves to an existing OBSERVATION-family record in the
    index. This check is independent of `armed` — it fires even when actuation IS armed, so a
    future caller can never emit an actuation event with no justifying observation, armed or
    not.
    """
    if not authorized and os.environ.get("FINOPS_KB_WRITE") != "1":
        raise RuntimeError(
            "knowledge write not authorized: set FINOPS_KB_WRITE=1 or pass authorized=True"
        )
    if message_family(event.source_type) == "actuation":
        if not armed and os.environ.get("FINOPS_ACTUATION_ARMED") != "1":
            raise RuntimeError(
                "actuation not armed: set FINOPS_ACTUATION_ARMED=1 or pass armed=True "
                "(today, nothing in the running system does either — this is a future hook)"
            )
        if not event.causes or not _resolves_to_observation(event.causes):
            raise RuntimeError(
                "actuation event missing or invalid `causes` — every actuation must cite "
                "the observation knowledge_id that justified it"
            )
```

Both new checks live inside the **single** shared `publish_event()` every producer already
calls (Delta 2). There is exactly one place to audit for "can actuation fire today," and the
answer, by inspection, is no: `FINOPS_ACTUATION_ARMED` is unset everywhere in this repo, and no
call site passes `armed=True`.

### 5d. What this design explicitly does not build (extends round 1's Scope Boundary)

- No semantic safety validator of *which* actuation is wise (a real control rule with
  `requires: [confidence, regret, ...]`) — future work, gated by the same measure-before-policy
  ordering as every other policy arm.
- No UI, CLI flag, or admin route to flip `FINOPS_ACTUATION_ARMED` — arming is a deploy-time
  environment decision, never a runtime toggle, so there is no "arm actuation" button to audit
  for misuse.
- No `CAUSED_BY` graph edge for `causes` in this round (the flat-index/CLI path is sufficient
  for the one-hop lookup this design needs today) — noted as the direct future analog of gap
  (d)'s `SUPERSEDES` edge fix, explicitly deferred.

---

## 6. Date spine + supersession — reused verbatim from round 1, one edge-write fix (gap d)

Fields (unchanged from round 1): `observed_at`, `indexed_at`, `valid_from` (written),
`valid_to` (always `null` in the artifact; computed at the index layer),
`lifecycle_state` (`current | superseded | tombstoned`, index-only, never stored in the
artifact). `supersedes`/`operation` semantics (`upsert`/`supersede`/`delete`) unchanged from
round 1 — see `docs/canonical_state_base_design.md` OQ2 for the full argument; nothing in Delta
1–3 changes this mechanism, only what feeds it (§8).

**Gap (d) fix — `kb-neo4j-v1`'s `SET` clause, extended.** Confirmed live at
`scripts/kb_worker.py:105-134`: the current clause sets exactly eleven properties
(`entity_id, text, source_uri, authority, commit_sha, source_type, logical_locator, language,
evidence_class, repository_id, acl_scope`) and silently drops
`valid_from`/`valid_to`/`observed_at`/`indexed_at`/`supersedes`. Required change:

```cypher
MERGE (k:Knowledge {knowledge_id: $id})
SET k.entity_id = $eid, k.text = $text, k.source_uri = $uri,
    k.authority = $authority, k.commit_sha = $commit,
    k.source_type = $stype, k.logical_locator = $loc,
    k.language = $lang, k.evidence_class = $ev,
    k.repository_id = $repo, k.acl_scope = $acl,
    k.valid_from = $valid_from, k.observed_at = $observed_at,
    k.indexed_at = $indexed_at, k.supersedes = $supersedes,
    k.causes = $causes                                        -- round 2 addition
WITH k
FOREACH (_ IN CASE WHEN $supersedes IS NOT NULL THEN [1] ELSE [] END |
    MERGE (prev:Knowledge {knowledge_id: $supersedes})
    MERGE (k)-[:SUPERSEDES]->(prev)
)
```

`valid_to`/`lifecycle_state` remain **index-only, computed at read time** — never a stored
artifact or graph property, exactly as round 1 specified; the gap was only that the *storable*
fields were never wired through, and `SUPERSEDES` (round 1 named the edge type in its OQ4 table
but never gave it Cypher) now has an actual write path.

---

## 7. Base-gap closures (a)–(c) — schema-level

### 7a. Gap (a), Finding 4 — `ledger_ingestion` no-session fallback

```python
def derive_ledger_records(
    story_result: dict,
    opencode_session_row: dict | None,     # None on claude_cli-backend runs — now a real branch
    summary_entry: dict,
    *,
    repository_id: str,
    now: str | None = None,
) -> list["KnowledgeRecord"]:
    """One ledger_job + one-or-more ledger_attempt records per cell.

    Primary path: join story_result + opencode_session_row + summary_entry by
    story_id/worktree_name (unchanged from round 1 — the DB row is authoritative when present).

    FALLBACK (round 2, closes Finding 4): when opencode_session_row is None, read
    tokens/cost/confidence directly from story_result["sessions"][i]["agentic"] — every field
    the DB join would have supplied is already there (story.py:261-279:
    prompt_tokens, completion_tokens, reasoning_tokens, answer_tokens, explanation_tokens,
    total_tokens, estimated_cost_usd, cache_read_tokens, cache_write_tokens, context_tokens,
    confidence), because StoryResult.agentic is backend-agnostic (story.py:217). evidence_class
    stays "[M]" — this is still measured, not degraded — but extractor_version is set to
    "ledger/v1-storyfallback" instead of "ledger/v1", so a downstream cost rollup can
    distinguish join-sourced from self-reported attempts without a new field.
    """
```

| Path | Source of tokens/cost/confidence | `extractor_version` | `evidence_class` |
|---|---|---|---|
| `opencode_session_row` present | DB join (unchanged, round 1) | `"ledger/v1"` | `[M]` |
| `opencode_session_row is None` | `story_result.sessions[i].agentic.*` | `"ledger/v1-storyfallback"` | `[M]` |

### 7b. Gap (b), Finding 5 — `meta_*` pollution named and routed

Classification runs **before** emission, inside `ledger_ingestion.py`, using the same
`EXPERIMENT_SESSION_PATTERNS` list `analyze_worktrees.py:32` already imports (the exact list
whose "batch" substring already false-matches `meta_batch_*`):

```python
def classify_session(session_title: str) -> str:
    """Return the source_type a session's ledger record should be emitted as.

    Runs BEFORE emission (not after) so a meta_* title is routed to "meta_session" at
    registration time — it never enters "ledger_attempt" in the first place, which is what
    prevents this design from relocating analyze_worktrees.py's title-substring pollution
    into the registry's own cost rollups instead of eliminating it.
    """
    if session_title.startswith("meta_"):        # covers meta_batch_* too — checked first,
        return "meta_session"                     # so it never reaches the pattern-list check
    if any(p in session_title.lower() for p in EXPERIMENT_SESSION_PATTERNS):
        return "ledger_attempt"
    return "ledger_attempt"   # unclassified titles still register — see round 1 OQ1, unchanged
```

`meta_session` records: `authority = ADVISORY`, `evidence_class = "[H]"`, own `source_uri`
namespace (`meta_session:{session_id}`, §3) — filterable out of cost rollups by `source_type`,
never by a fragile title match at query time.

### 7c. Gap (c), Finding 2 — remediate the lost ~83 `_results_summary.json` entries

One-time migration step (§9, step 5) — not a steady-state mechanism, since the source is git
history, not a live write path:

```
1. git show <pre-shrink-commit>:experiments/results/_results_summary.json  →  227 entries
2. diff by `experiment` key against the current 144-entry file             →  ~83 extra entries
3. for each extra entry:
     operation = "upsert"
     source_type = "story"  (or "ledger_job" if it maps more directly to that schema)
     evidence_class = "[M]"   (unchanged — genuinely measured)
     reason = "recovered from git history <sha>; manifold/semantic labels and
               cross-matched baselines are known-stale as of the 227→144 shrink"
     # reason on an upsert (not a delete) is round 2's second use of the field —
     # a caveat annotation, distinct from round 1's tombstone-reason usage
4. cross-check story_id/cell_key against post-shrink 144 + pass-1/pass-2 backfilled entries:
     - if a legitimate rerun exists under a NEW story_id → REPLACED_BY edge to it
     - else → stays a caveated-but-canonical historical record (no tombstone;
       "the source worktree is gone; this is the best available fact, not a fiction")
```

---

## 8. Write-time registration — the four call sites (Delta 1)

Steady state: every producer emits inline, in the same process, immediately after its own
artifact write succeeds. No hourly scan originates a canonical record; `inventory.py refresh`,
`sync_data.py`, and `knowledge_stream.py`'s `reconcile_missing()` (`RECONCILE_INTERVAL_S = 3600`)
remain **re-delivery** mechanisms for events the stream already has, never **origination**
mechanisms for events that were never emitted.

| Call site | File:line (confirmed) | Inline call added |
|---|---|---|
| Story result write | `src/instrument/story.py:945 save_story_result()` | `story_ingestion.derive_story_records(result, repository_id=...)` → `publish_event(..., authorized=True)`, after `path.write_text()` succeeds, same function |
| Single-task result write | `scripts/run.py:379` | Same pattern — story-record-equivalent emit, inline after `path.write_text()` |
| Review write | `finalize_reviews.py`, per `review_{story_id}.json` write | `review_ingestion.derive_review_records(review, repository_id=...)` → `publish_event(...)`, inline after write |
| Supervisor verdict | `scripts/supervise.py:314 supervise_once()` | `observation_ingestion.derive_observation_record(verdict, repository_id=...)` → `publish_event(...)`, called for **every** verdict — the `status not in ("healthy", "unknown")` check at `supervise.py:343` continues to gate `flag`-record emission only, unchanged; it is no longer the gate for `observation`-record emission |

Batch backfill (`derive_*_records` walking existing files) is retained **only** for the
Migration plan's one-time steps (§9, steps 2–5), covering the pre-Delta-1 corpus — never re-run
as a steady-state mechanism once this design ships.

---

## 9. Store split (updated from round 1 OQ4)

| Layer | What lives there | Round-2 change |
|---|---|---|
| **Immutable files** | Story/review JSONs (unchanged, pointer-only); new artifact files only for record types with no pre-existing file (`ledger_job`, `ledger_attempt`, `observation`, `flag`, `meta_session`, `actuation`) | `actuation` and `meta_session` join the "new artifact file" set — same "point, don't copy" rule everywhere else |
| **Neo4j** | `Knowledge` nodes + `SUPERSEDES`/`CLEARED_BY`/`REPLACED_BY` edges | §6's `SET`-clause fix (gap d) — `valid_from`/`observed_at`/`indexed_at`/`supersedes`/`causes` now actually persist, and `SUPERSEDES` now has a write path |
| **Parquet** | Unchanged role; `entity_id`/`knowledge_id` join columns (round 1) | No change |
| **Manifest** (`registry` array, backed by `registry_index.jsonl`) | Flat index: one row per `entity_id` | No schema change — `source_type` now ranges over 9 values instead of 6; `causes` surfaces on `actuation` rows only |

---

## 10. Surfacing (unchanged mechanism from round 1, extended coverage)

`scripts/registry.py show/query/lineage` and `GET /api/registry*` (round 1, unchanged shape) now
additionally: (a) resolve `meta_session` as a distinct, filterable `--record-type`, and (b) for
an `actuation` record, `show <id>` follows `causes` and prints the justifying observation inline
— "why did the system decide to act" stays a one-hop lookup even though nothing exercises this
path today. Both routes remain `GET`-only; nothing added here calls `send_input`/`interrupt` or
touches `OpenCodeClient` — the flag-only rail is unchanged as **today's default**, and Delta 3's
actuation family is inert (§5c) precisely so that this remains true without this design having
to hard-code "never."

---

## 11. Backward compatibility — restated as a checklist

- [x] No existing story/review/result JSON is rewritten. Registration is pointer-only wherever a
  file already exists (`story`, `review`, `flag`); new artifact files are written only for
  record types with no pre-existing file.
- [x] `KnowledgeRecord`/`KnowledgeEvent` field additions (`supersedes`, `reason`, `causes`) are
  all trailing-default, appended after the existing trailing-default fields — verified against
  the live field order in `src/instrument/knowledge.py`, not assumed.
- [x] The manifest's existing `files{}` block is unchanged; `registry` remains a new, additive
  array.
- [x] `retrieve()`'s ranking, fusion, and per-cell scope logic are untouched — new `source_type`
  values slot into the existing `Authority` ordering with no new retrieval behavior.
- [x] The flag-only rail is unchanged as today's default: zero call sites construct an actuation
  record, `FINOPS_ACTUATION_ARMED` is unset everywhere in this repo, and the gate lives in one
  audited place (`publish_event()`).

---

## 12. Migration plan (ordered; one-time vs. steady-state explicitly separated)

Steps 1–2 are schema/infrastructure (additive-only). Steps 3–6 are the **one-time** backfill of
the pre-Delta-1 corpus, explicitly not re-run once Delta 1's inline call sites are live. Step 7
wires Delta 1's inline call sites themselves (the one step that touches currently-running
producers, ordered after backfill so inline emission is exercised against a codebase already
proven against static fixtures). Step 8 wires the two Δ3 gates (still inert — no call site
added). Step 9 wires the surfaces last.

1. **Schema additions.** `causes` on `KnowledgeRecord`/`KnowledgeEvent`; the three new
   `source_type` values (`meta_session`, `actuation`, plus round 1's still-pending
   `ledger_job`/`ledger_attempt`/`observation`/`flag` if round 1 hadn't already landed them);
   `"kb-registry-v1"` added to `CONSUMER_GROUPS`; the `kb-neo4j-v1` `SET`-clause fix (§6, gap d).
   Run the existing KB test suite to confirm the 1,913 existing artifacts still parse.
2. **Build producer modules**: `story_ingestion.py`, `review_ingestion.py`,
   `ledger_ingestion.py` (with the no-session fallback, §7a, and the `meta_*` classifier, §7b),
   `observation_ingestion.py`, `actuation_ingestion.py` (§5b — built, unit-tested, zero call
   sites). Unit-test each against a fixed sample of real files, including a claude_cli-backend
   fixture for `ledger_ingestion.py` specifically (closes gap a at the test layer, not just the
   code layer).
3. **Backfill pass 1 — unambiguous canonical records.** All 156 main-repo story JSONs, reviews,
   valid `_results_summary.json` entries. `upsert`, `lifecycle_state → current`.
4. **Backfill pass 2 — un-folded single-task results (finding 3).** The 2026-08-17 results,
   registered exactly like pass 1, independent of whether `analyze_worktrees.py` ever re-runs.
5. **Backfill pass 3 — stranded results (finding 1) + lost-83 remediation (gap c, §7c).** Both
   are one-time, git/worktree-sourced backfills: point the story producer at both stranded
   worktrees (worktree-independent identity makes a byte-identical duplicate a free no-op); run
   the `git show`-based recovery for the 83 lost `_results_summary.json` entries, caveated via
   `reason` on `upsert` per §7c.
6. **Tombstone pass — 77 contaminated cells + `meta_*` reclassification (gap b, §7b).** Register
   each `_remediation_contaminated/` file as `delete` with a forensic `reason`; separately, audit
   `_results_summary.json`/`inventory.json` for any `meta_*`/`meta_batch_*` title that already
   false-matched the experiment-session pattern and register each as a tombstoned
   `ledger_job`/`ledger_attempt` with `reason="meta-analysis session misclassified..."`.
7. **Wire Delta 1's inline call sites** (§8) — `story.py:945`, `run.py:379`,
   `finalize_reviews.py`, `supervise.py:314`. This is the first step touching a currently-live
   write path; landing it after steps 3–6 means inline emission is proven against producer
   modules already validated on the real backfilled corpus, not synthetic fixtures.
8. **Wire the two Δ3 gates** (§5c) inside `publish_event()` — `FINOPS_ACTUATION_ARMED` check,
   `causes`-resolves-to-observation check. No call site is added to `supervise.py` or
   `workflow_runner.py` in this step; a dedicated test asserts zero such call sites exist.
9. **Wire the surfaces** — extend `generate_manifest.py`, add `scripts/registry.py`, add
   `/api/registry*` + the Control Room panel, now covering all 9 `source_type` values including
   `meta_session` filtering and `actuation`'s `causes` lineage display. Last, so it's built and
   tested against the real backfilled + inline-registered corpus from steps 3–7 rather than
   synthetic fixtures.

---

## 13. Scope boundary (restates round 1's, adds two Δ3-specific exclusions)

Everything in round 1's Scope Boundary (`docs/canonical_state_base_design.md`, closing section)
holds unchanged: no new mutating Control Room route, no rewriting/relocation of existing JSONs,
no graph/lineage visualization beyond a flat chronological list, no re-scoring of contaminated
cells, no changes to `retrieve()`'s ranking/fusion, no real-time guarantee, no persisted
transcript for the monitor session, no unification of the two Neo4j schemas. Round 2 adds:

- **No actuation call site.** `actuation_ingestion.py` is built and tested; nothing in
  `scripts/supervise.py` or `src/instrument/workflow_runner.py` calls it. Wiring a call site is
  explicitly future work, gated by a compiled control rule (§5b) — not part of this design.
- **No semantic actuation-safety validator.** The gate in §5c is a pure allow/deny switch keyed
  on an environment flag and a lineage check; it does not evaluate *whether* a given actuation
  candidate is wise. That is a `requires`/`produces`-gated control rule, future work.
