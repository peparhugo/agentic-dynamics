---
status: accepted
---
# Restructuring + Refactoring Review

Phase 1 (restructure) of `repo_review_fable`. Builds on DeepSeek's prior architecture review
(`docs/arch_review/{architecture_map,coupling_assessment,refactor_roadmap,review_verify}.md`,
read at `/tmp/pipeline/feature_architecture-review/docs/arch_review/` — that branch was never
merged, so its `docs/arch_review/` artifacts do not exist on `main`; this document reproduces the
references it extends). It is a **delta**, not a re-derivation: it flags what changed since that
review was written, what the merged canonical-state code actually looks like as shipped, and what
DeepSeek got wrong or missed. Every file:line is re-read from current source.

---

## 1. The headline delta: the KB write path is no longer "cold"

DeepSeek's coupling assessment concluded (§1.4) that the authority contract was *"correct but
cold — bypassed on the hot write path; honored only at a cold, post-hoc ETL boundary."* That
verdict is now **stale**. The canonical-state rounds (Delta 1) have since wired write-time
registration into four live production call sites:

| Call site | Emits | Evidence |
|---|---|---|
| `story.save_story_result` | one `source_type=story` event per saved result | `src/instrument/story.py:971-980` |
| `scripts/run.py` result save | one `story` record via `derive_story_records_from_run_output` | `scripts/run.py:389-396` |
| `scripts/finalize_reviews.py` | one `source_type=review` event per merged review | `scripts/finalize_reviews.py:70-86` |
| `scripts/supervise.py` `supervise_once` + `emit_flag` | one `observation` per verdict + one `flag` per non-healthy verdict | `scripts/supervise.py:262-275`, `:381-400` |

So the "one typed stream" is now warm on the story/supervisor/review paths, and the apparatus →
knowledge edge that DeepSeek's §1.2 said did not exist now exists in four places. Two consequences,
both new and both unaddressed:

1. **There is still no single write path — there are four inline copies of the same five-line
   emit block.** Each call site does `from .knowledge_ingestion import REPOSITORY_ID,
   record_to_event; from .knowledge_stream import connect, publish_event; from .X_ingestion import
   derive_X` *inside a function body* (the function-local import is a circular-import dodge, see
   §3.1), then `for record in derive(...): publish_event(r, record_to_event(record),
   authorized=True, source_type=record.source_type)`. The four copies differ only in
   availability posture (story/run/finalize_reviews let a downed stream **raise**; supervise
   wraps it in `try/except` — each documents the divergence at length). DeepSeek's D1
   ("one ledger write path") is therefore only *half* delivered: the pointer is emitted at
   source, but the emit itself is copy-pasted, not factored.

2. **The `source_type` vocabulary is now split across three overlapping registries, none
   complete.** `knowledge.py:100-124` defines `OBSERVATION_TYPES`/`ACTUATION_TYPES`/
   `message_family()` — but `OBSERVATION_TYPES` lists only `{story, review, ledger_job,
   ledger_attempt, observation, flag, meta_session}` and **omits** the round-1 producer types
   `finding`/`code`/`report`/`policy`. Each producer module then defines its own
   `SOURCE_TYPE`/`EXTRACTOR_VERSION`/`ACL_SCOPE` constants, which the barrel re-exports under
   prefixed aliases (`STORY_SOURCE_TYPE`, `CODE_SOURCE_TYPE`, `QUALITY_SOURCE_TYPE`,
   `POLICY_SOURCE_TYPE`, `REVIEW_SOURCE_TYPE`, `LEDGER_SOURCE_TYPE_*`, `SOURCE_TYPE_OBSERVATION`,
   `ACTUATION_SOURCE_TYPE` — `__init__.py:211-314`). And `scripts/registry.py:59-62` declares a
   *third* list, `RECORD_TYPES`, that deliberately excludes the round-1 types. The
   `message_family()` default ("anything unregistered is observation") masks the omission — it
   classifies correctly *by accident* — but "one typed stream" has no single place that owns the
   type field.

---

## 2. Canonical-state: is the one-typed-stream split clean, or did it leak?

**Verdict: the *contract* is clean; the *construction* leaked.** The design's central claim —
`source_type` + `operation` are the only discriminators, one pointer envelope, one idempotent
`knowledge_id` key — holds *transport*-side. The load-bearing primitives stay centralized:

- `knowledge.py` — `KnowledgeEvent` (pointer-only, no body, `knowledge.py:178-239`),
  `KnowledgeRecord` (frozen, 30 fields, `:242-360`), the two sha256 ids, the `Authority` ordinal.
- `knowledge_stream.py` — `publish_event` with the three orthogonal gates (write guard →
  actuation-armed → lineage `causes`-must-resolve-to-observation, `:128-194`); `process_entry`
  (read → verify → extract → upsert → XACK, `:387-428`).
- `knowledge_ingestion.py` — the one pointer contract `record_to_artifact → record_to_event →
  extract_record` (`:226-424`) that all producers reuse.

But the *producer side* leaked badly. The five new canonical-state producer modules
(`story_ingestion`, `review_ingestion`, `ledger_ingestion`, `observation_ingestion`,
`actuation_ingestion`) are ~60% identical boilerplate each. Concretely:

- `_now_iso` + `_sha256_bytes` are re-defined verbatim in **all five**:
  `story_ingestion.py:77-84`, `review_ingestion.py:58-63`, `ledger_ingestion.py:132-137`,
  `observation_ingestion.py:59-64`, `actuation_ingestion.py:72-77`.
- The "build with placeholder ids → serialize → hash → `replace()` back-fill" dance (a
  ~25-line block) is copy-pasted into every `build_*_record`:
  `story_ingestion.py:175-208`, `review_ingestion.py:109-142`, `ledger_ingestion.py:215-248`,
  `observation_ingestion.py:110-143`, `actuation_ingestion.py:143-176`, and already in
  `knowledge_ingestion.py:315-355`, `code_ingestion.py`, `quality_ingestion.py`,
  `policy_ingestion.py`. Nine copies of the same ordering subtlety (the reason the derived ids
  and volatile timestamps must be blanked before hashing — which is exactly the kind of
  invariant that silently breaks in the *next* producer).
- `_source_revision` (`ledger_ingestion.py:148-160`) re-implements `knowledge_ingestion._git_sha`
  (`:130-141`) — the identical "first non-empty of `git_sha`/`commit`/`commit_sha`" loop.
- The `derive_*_records`-returns-`[]`-on-missing-id pre-filter convention is restated as a fresh
  docstring in each module.

This is the single highest-leverage restructuring target in the KB: **one shared
record-builder factory** (see R1) would delete ~300 lines of duplicated, correctness-sensitive
boilerplate and make "add a source_type" a one-line table entry instead of a 150-line
copy-paste module.

### The two genuine *cross-boundary* leaks (not just duplication)

**L1 — `ledger_ingestion.py` imports `scripts/` at import time.** `_load_experiment_session_patterns`
(`ledger_ingestion.py:79-103`) uses `importlib.util.spec_from_file_location` to exec
`scripts/_constants.py` from a core library module. The docstring concedes it is a hack to avoid
inverting the `scripts → src` dependency. This is the only place a `src/instrument` module
reaches out of the package into the scripts tree, and it runs at **module import** (line 103 is
a module-level call), so `import instrument` now depends on the `scripts/` directory layout
existing. Worse, the value it loads is consumed by a **dead branch**: `classify_session`
(`ledger_ingestion.py:106-126`) has both its `if any(p in ...)` branch and its fallthrough
`return SOURCE_TYPE_ATTEMPT`, so `EXPERIMENT_SESSION_PATTERNS` never changes any output — the
whole load (and the "identical list" guarantee it exists to provide) is dead code. The gap-(b)
fix is real only in the `meta_` prefix short-circuit at line 122.

**L2 — `kb_worker.py`'s flag auto-clear rule re-parses producer prose.** `_cell_id_and_status_from_observation_text`
(`scripts/kb_worker.py:128-158`) recovers `(cell_id, status)` by string-splitting the rendered
`text` field that `observation_ingestion.build_observation_record` formats as
`f"{cell_id} [{model}]: {status} — {why}"` (`observation_ingestion.py:108`). The consumer thus
hard-depends on the producer's prose format: a change to the render string silently breaks the
auto-clear rule (returns `(None, None)` → no-op), with no type system or test to catch it. The
producer *had* `cell_id` and `status` structurally; the fact that the observation record's
`entity_id` deliberately folds `cell_id` into a one-way hash means the only durable correlation
left is the text. This is a real leak of a *structured* fact into an *unstructured* field that a
downstream consumer then has to parse back out.

---

## 3. Recommended restructuring (ranked)

Each names the module, the seam, the before/after, and the expected effect. R1–R3 are KB-local
and safe; R4–R6 are the "one write path" / cross-boundary fixes; R7–R9 extend DeepSeek's debt
list with what has drifted since.

### R1 — A single `RecordBuilder` factory (kill the 9-copy boilerplate)

- **Module/seam:** new `src/instrument/record_factory.py` (or fold into `knowledge_ingestion.py`
  as a `build_record_from_parts(...)` helper); consumed by `knowledge_ingestion`, `code_ingestion`,
  `quality_ingestion`, `policy_ingestion`, `story_ingestion`, `review_ingestion`,
  `ledger_ingestion`, `observation_ingestion`, `actuation_ingestion`.
- **Before:** nine modules each re-implement `_now_iso`/`_sha256_bytes` and the
  placeholder-ids→`record_to_artifact`→`compute_knowledge_id`→`replace()` back-fill
  (`story_ingestion.py:175-208`, `ledger_ingestion.py:215-248`, `observation_ingestion.py:110-143`,
  etc.).
- **After:** one `build_record(*, source_type, source_uri, logical_locator, repository_id,
  revision, authority, evidence_class, text, extra_fields: dict, now=None) -> KnowledgeRecord`
  that owns the ordering invariant once. Each producer keeps only its *derivation* (how it maps
  its input dict to `text` + structured fields) and calls the factory.
- **Effect:** ~300 lines deleted; the content-hash-back-fill subtlety (blank `knowledge_id`/
  `content_hash`/`valid_from`/`observed_at`/`indexed_at` before hashing) is correct in one place
  instead of nine; a tenth producer is a one-line call. **Independent of everything else — land
  first.**

### R2 — Centralize the `source_type` vocabulary

- **Module/seam:** `knowledge.py` (the contract leaf) becomes the single owner of the type
  registry; `__init__.py`'s prefixed aliases and `scripts/registry.py`'s `RECORD_TYPES` fold in.
- **Before:** three overlapping lists — `OBSERVATION_TYPES`/`ACTUATION_TYPES`
  (`knowledge.py:100-124`, omits `finding`/`code`/`report`/`policy`), per-module `SOURCE_TYPE`
  constants re-aliased in the barrel (`__init__.py:211-314`), and `registry.RECORD_TYPES`
  (`registry.py:59-62`, which explicitly excludes round-1 types).
- **After:** one `SOURCE_TYPES` mapping (name → `(message_family, authority, evidence_class)`)
  in `knowledge.py`; `message_family()` keys off it; `registry.py` derives its `--record-type`
  choices from it instead of hard-coding an exclusion.
- **Effect:** "one typed stream" regains a single source of truth for the type field; the
  `message_family` default stops silently papering over an unregistered type. **Depends on R1**
  (the factory carries `source_type` through one place).

### R3 — Delete the `scripts/` reverse-import and its dead branch

- **Module/seam:** `ledger_ingestion._load_experiment_session_patterns` + `classify_session`
  (`ledger_ingestion.py:79-126`).
- **Before:** `importlib` exec of `scripts/_constants.py` at module import (`:79-103`); the loaded
  list feeds a branch that returns the same value as its fallthrough (`:122-126`), so it is dead.
- **After:** move `EXPERIMENT_SESSION_PATTERNS` into `src/instrument/` (e.g. a small
  `session_types.py`, or the `experiment_spec` vocabulary — see R9), have `scripts/_constants.py`
  import *it* (reversing the edge to the correct direction), and make `classify_session` a real
  two-way discriminator or collapse it to the `meta_` prefix check it actually is today.
- **Effect:** removes the only `src → scripts` dependency and the only module-import-time
  exec; `import instrument` no longer assumes the scripts tree layout. **Fold into R9's task-type
  vocabulary work.**

### R4 — One shared write-path helper (finish DeepSeek's D1)

- **Module/seam:** new `src/instrument/emit.py` (or a `register_records(records, *,
  authorized=False)` function in `knowledge_stream.py`); replace the four inline emit blocks.
- **Before:** four near-identical `from … import connect, publish_event, record_to_event,
  derive_*` function-local imports + loop (`story.py:971-980`, `run.py:389-396`,
  `finalize_reviews.py:70-86`, `supervise.py:262-275`/`:381-400`), each hand-rolling the
  write-guard and the availability posture.
- **After:** `register_records(records, *, fail_loud: bool)` — one function that does
  `derive → record_to_event → publish_event(authorized=True)`, with a single parameter for the
  "raise vs swallow a downed stream" posture. The four call sites call it; each keeps only its
  derivation (which producer function, which input).
- **Effect:** the "one typed stream" gets one *write* path to match its one *transport*;
  changing the emit contract (e.g. adding a future `supersede`/`delete` default) touches one
  place instead of four. **Ordered after R1** (so the helper takes records, not dicts).

### R5 — Promote the observation `cell_id`/`status` into a structured field

- **Module/seam:** `observation_ingestion.build_observation_record` (`:110-143`) + `kb_worker._cell_id_and_status_from_observation_text`
  (`:128-158`).
- **Before:** `cell_id` and `status` exist only inside the hashed `entity_id` and the rendered
  `text`; the consumer parses the text back out to run the auto-clear rule.
- **After:** add a `subject_id` (and `subject_status`) field to `KnowledgeRecord` (trailing
  default, same backward-compat pattern as `causes`/`supersedes` at `knowledge.py:285-290`),
  populate it structurally in the observation/flag producers, and have `kb_worker` read it
  instead of splitting prose.
- **Effect:** the auto-clear rule stops depending on a render format; producer text can change
  freely. This is the cleanest way to close L2 — it removes the leak rather than pinning the
  format. **Do in the same change as R1** (both touch the producer field surface).

### R6 — Stop hand-syncing `REGISTRY_INDEX_PATH` and `KB_ARTIFACT_DIR`

- **Module/seam:** `scripts/kb_worker.py:50,62`, `scripts/generate_manifest.py:22`,
  `scripts/kb_produce.py:54`, `scripts/kb_produce_registry.py:67`, `knowledge_ingestion.ARTIFACT_DIR:68`.
- **Before:** four copies of `experiments/results/kb` and two copies of
  `experiments/results/registry_index.jsonl`, each with a "duplicated, not imported, keep in sync
  by hand" comment.
- **After:** a single `paths.py` (or constants on `knowledge_stream.py`/`knowledge_ingestion.py`)
  that these scripts import; the "dependency-light" argument for `generate_manifest.py` (its
  comment at `:13-21`) is addressable with a value-only import that doesn't pull `redis`.
- **Effect:** one path change can no longer silently desync producer and consumer artifact
  locations (a real data-loss vector — the consumer `read_artifact` would 404 on a path drift).

### R7 — Split `workflow_runner.py`'s RAG seam (DeepSeek D2, still open)

- **Module/seam:** `workflow_runner.py` (820 lines) → new `src/instrument/augment.py`.
- **Before:** phase execution, the `retrieve → construct → render` augmentation, and self-build
  emit share one module. Note the RAG imports are now *lazy* (the top-level imports at
  `workflow_runner.py:42-54` are only `backends`/`experiment_spec`/`language`/`live`/
  `step_routing`/`test_runner` — `retrieval`/`prompt_constructor` are imported inside the
  rag-gated path), so the fan-out has already been thinned; the remaining problem is
  *responsibility*, not import count.
- **After:** `augment.augment_prompt(...) -> AugmentationOutcome` as a standalone module.
- **Effect:** the KB stays testable without a workflow run; `workflow_runner` drops to phase
  execution + emit. **Unchanged from DeepSeek's ordering: after the seam is exercised.**

### R8 — Collapse the two "reshape a non-StoryResult into a StoryResult" adapters

- **Module/seam:** `story_ingestion.derive_story_records_from_run_output`
  (`story_ingestion.py:232-285`) and `kb_produce_registry._summary_entry_to_story_result`
  (`kb_produce_registry.py:224-247`).
- **Before:** two independent field-renaming adapters that both synthesize a
  `StoryResult`-shaped dict from a *different* upstream shape (`run.py` output vs a recovered
  `_results_summary.json` entry), each with its own identity rationale.
- **After:** one `adapt_to_story_result(source: dict, *, kind: "run"|"summary")` helper; the two
  call sites pass a `kind` and share the identity formula.
- **Effect:** one place owns "what is the canonical story_id for a non-story artifact", which is
  precisely the thing that must not drift if cross-seed comparison (DeepSeek's seed-repo goal)
  is to be trustworthy.

### R9 — One task-type vocabulary (DeepSeek D4) — now *needed* by R3

- **Module/seam:** `story.SessionSpec.task_type`, `routing.normalize_task` (`routing.py:16`),
  `_constants.normalize_task` (`_constants.py:53`), `_constants.EXPERIMENT_SESSION_PATTERNS`
  (`_constants.py:23`).
- **Before:** the duplicated `normalize_task` and the hard-coded session-pattern list — the same
  list R3's reverse-import currently exec's out of `_constants.py`.
- **After:** a single `TaskType`/session-pattern definition in `experiment_spec` (or a new
  `session_types.py`); `routing`, `story`, and `ledger_ingestion` import it; the `_constants.py`
  helpers are deleted.
- **Effect:** resolves the R3 reverse-import at its root (the list lives where its consumers
  are), removes the `normalize_task` duplication, and makes foreign-task routing correct.

---

## 4. What DeepSeek got wrong or missed

1. **"Authority contract is cold / bypassed on the hot write path" is now false** (§1.4 of the
   coupling assessment). The write-time registration is live in four call sites. What DeepSeek
   missed is that it landed as *four inline copies* (R4) with function-local imports — the
   apparatus→knowledge edge now exists in `story.py`/`run.py`/`finalize_reviews.py`/
   `supervise.py`, not just `workflow_runner.py`.

2. **"The ONLY KB writer is the opt-in `emit_self` path" is now false.** The same assessment's
   claim that `retrieve → construct → render` references `publish_event` zero times still holds,
   but the "only writer" framing is gone: `story.py`, `run.py`, `finalize_reviews.py`,
   `supervise.py`, and the three `kb_produce*` scripts all write now. The *isolation* invariant
   (per-cell `repository_id`, two Redis planes, observe-only supervisor) is intact; the
   *uniqueness* claim is not.

3. **DeepSeek did not anticipate the producer-boilerplate explosion.** Its architecture map
   (52 modules, 20,498 LOC) predates the five canonical-state producers; the package is now 58
   modules. The single biggest *new* debt — the nine-copy record-build dance (R1) — is not in the
   roadmap and is more mechanical-currency than any of its D4–D7 items.

4. **`src/instrument/CONTEXT.md` and the mental-model are stale on the KB surface.** CONTEXT.md's
   "Runtime RAG / Knowledge Base" section documents `knowledge`/`knowledge_stream`/
   `knowledge_ingestion`/`code`/`quality`/`policy` but has **zero** mention of
   `story_ingestion`/`review_ingestion`/`ledger_ingestion`/`observation_ingestion`/
   `actuation_ingestion` (confirmed: 0 matches for all five), the `message_family`/
   observation-vs-actuation split, or the registry/tombstone/compaction machinery. It also still
   says "40 Python modules"; the real count is 58. The mental-model's ledger table does not list
   the `supersedes`/`causes` fields. **Recommendation:** the canonical-state docs
   (`docs/canonical_state_*_design.md`) are the source of truth but are not linked into the
   load-bearing CONTEXT; fold a one-paragraph summary + the five new modules into
   `src/instrument/CONTEXT.md` (and the mental-model KB section) as part of this review's follow-up.

5. **DeepSeek's `D7` (delete deprecated modules) and `Step 0/D3` (`RESULTS_ROOT`) are still
   unaddressed and now more costly.** `adapter.py`/`experiment.py`/`lab_book.py` still exist
   (confirmed), and the hard-coded `experiments/results` count has *grown* from 47 to **49**
   scripts. The seed-repo workstream (Step 0) is the blocker for the entire seed goal and has not
   moved; nothing in the canonical-state rounds depends on it, so it remains the correct next
   cross-cutting step, but it should be sequenced *before* any further KB producer work so new
   producers don't add a 50th hard-coded path.

6. **`kb_produce_registry.py` is a "one-time" script that shipped at 526 lines and will live
   forever.** It carries `STRANDED_WORKTREES` with two hard-coded absolute `/tmp/pipeline/...`
   paths (`kb_produce_registry.py:92-95`) and a `--since-sha` operator-judgment requirement. As a
   migration driver that's fine, but it is structurally indistinguishable from the steady-state
   `kb_produce_sources.py` (same `_SOURCES` dict, same `emit_records`, same `sys.path` bootstrap).
   **Recommendation:** mark it `scripts/archive/` after the migration completes (or gate its
   `main` on an explicit `--i-know-this-is-one-time`), so future readers don't mistake it for a
   second, divergent producer to extend.

---

## 5. Do NOT do (building on DeepSeek §3, unchanged except where noted)

1. **Do not promote the `text`-parsing in `kb_worker._cell_id_and_status_from_observation_text`
   into a "shared" convention.** It is the symptom, not the pattern — fix it with R5, don't
   standardize it. (New — this is a canonical-state-specific trap DeepSeek couldn't see.)
2. **Do not add a `source_type` field to `KnowledgeEvent`** to "solve" lineage. Round 2 already
   reasoned through this (plumbing option (b), `knowledge_stream.publish_event` docstring,
   `:148-156`) and passed `source_type` as a keyword instead. The registry index
   (`SOURCE_TYPE_INDEX_KEY`) is the right self-contained mechanism; R2 should formalize it, not
   replace it.
3. **Do not merge the two Redis planes, re-rank authority, fabricate `0.0`, replace
   `test_runner.run_suite`, or re-invent transport** — DeepSeek §3 items 2/3/4/6/7 stand
   unchanged and were verified still holding in the merged code (`knowledge_stream` DB 2 vs
   `live` DB 1; `Authority` ordinal `knowledge.py:61-85`; `test_executed_success` measured-or-None
   `knowledge.py:276`).
4. **Do not convert the producer modules to a YAML/table-driven registry** to kill the
   boilerplate. That would trade code duplication for an implicit, harder-to-type-check data
   format and would weaken the per-module "why this authority/evidence class" reasoning the
   docstrings carry. R1's factory keeps the derivation *in code* and factors only the mechanics.

---

## 6. Ordering

| # | Change | Depends on | Parallelizable with |
|---|---|---|---|
| R1 | Record factory | — | R3, R6, R7 |
| R2 | source_type registry | R1 | R6 |
| R3 | remove reverse-import + dead branch | (R9 shares the list) | R1, R4, R6 |
| R4 | one write path | R1 | R5, R6 |
| R5 | structured `subject_id`/`subject_status` | R1 | R4, R6 |
| R6 | single paths module | — | R1–R5, R7 |
| R7 | split workflow_runner RAG seam | (none; sequence after the seam is exercised) | R6 |
| R8 | one StoryResult adapter | R1 | R3, R6 |
| R9 | one task-type vocabulary | R1 (shares the factory-adjacent surface) | R3 |

**Sequence:** `R1 → (R2, R4, R5, R8) → R3+R9 → R7`. `R6` lands anytime. Everything in R1–R9 is
KB-local or cross-boundary cleanup — none touches the measurement core (`perturb`/`solution`/
`basin`/`efficiency`/`strategy`/`recovery`) or the authority ordinal, so provenance and the
224+ game reports' comparability are preserved by construction.

---

*Reviewed at commit `1baff2a6f` (`feature/repo-review-deepseek`). DeepSeek's prior artifacts read
from the unmerged `feature/architecture-review` branch at
`/tmp/pipeline/feature_architecture-review/docs/arch_review/`.*
