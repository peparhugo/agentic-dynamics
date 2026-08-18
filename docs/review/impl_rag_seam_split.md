# R7 implementation trace — `impl_rag_seam_split.md`

Phase 3 (verify) of `rag_seam_split` (spec `experiments/specs/rag_seam_split.yaml`). Traces the
R7 split (`workflow_runner.py` → `augment.py`) and the docs refresh (`src/instrument/CONTEXT.md`
+ `.opencode/instructions/mental-model.md`). Every check re-reads the delivered files, not the
prior phases' prompts. Implement commit `376c17cb8`.

---

## 1. R7 — the seam split (restructure.md R7, DeepSeek D2)

`restructure.md` R7 asked for `workflow_runner.py` (820 lines) → a standalone `augment.py`, with
`workflow_runner` dropping to phase execution + emit. The RAG imports were already lazy
(`retrieval`/`prompt_constructor` imported inside the rag-gated path), so the split is a
responsibility cut, not a new import surface.

### 1.1 `augment.py` (new)

| # | Check | Result | Evidence |
|---|---|---|---|
| R7-a | Standalone module exists | **PASS** | `src/instrument/augment.py`, 265 lines |
| R7-b | Public entry point is `augment_prompt(...) -> AugmentationOutcome` | **PASS** | `augment.py:105` (def), `:49` (`AugmentationOutcome` dataclass) |
| R7-c | Default wiring moved with it | **PASS** | `default_retrieve_fn` (`:200`), `default_construct_fn` (`:240`), `DEFAULT_INHERITED_TOOLS` (`:35`), private `_attempt_id` (`:38`) + `_evidence_from_attempt` (`:71`) |
| R7-d | Module is pure w.r.t. the worktree, read-only | **PASS** | module docstring `:1-20`; `augment_prompt` returns on any failure with a named `fallback_mode` (`:188-196`); references `publish_event` zero times |
| R7-e | Lazy optional-dep imports preserved | **PASS** | `ChromaStore`/`Neo4jClient`/`retrieve` imported inside `default_retrieve_fn` (`:200-237`); `prompt_constructor` imports inside `augment_prompt`/`default_construct_fn` |

### 1.2 `workflow_runner.py` (trimmed)

| # | Check | Result | Evidence |
|---|---|---|---|
| R7-f | Drops to phase execution + emit | **PASS** | 820 → 587 lines; retains `run_workflow` (`:270`), `cell_scope` (`:242`), `_emit_self_finding` (`:254`), `PhaseResult` (`:65`), `WorkflowRunResult` (`:138`), `_build_phase_prompt` (`:173`), git helpers (`:179-235`) |
| R7-g | Imports from `augment`, no longer defines them | **PASS** | `from .augment import ...` (`:44`); call site `augment_prompt(` (`:467`), `default_retrieve_fn()` (`:476`), `default_construct_fn(...)` (`:477`) |
| R7-h | Old private names gone | **PASS** | `grep _augment_prompt\|_default_retrieve_fn\|_default_construct_fn\|AugmentationOutcome` over `workflow_runner.py` → 0 matches (only `PhaseResult` provenance field names remain) |
| R7-i | `PhaseResult` provenance fields preserved byte-compatible | **PASS** | fields `:87-96`; `to_dict()` serialization `:121-130`; population from `AugmentationOutcome` `:466,480-483` (incl. `pre_phase_commit`, `fallback_mode`, all `augmentation_*`) |
| R7-j | Barrel re-export | **PASS** | `__init__.py` imports `AugmentationOutcome`/`augment_prompt`/`default_retrieve_fn`/`default_construct_fn`/`DEFAULT_INHERITED_TOOLS` from `.augment` (`:405-410`), added to `__all__` (`:490-491`) |

### 1.3 Read-only invariant (the load-bearing guarantee)

The existing test `test_retrieve_construct_render_path_never_writes` now asserts the invariant
against the moved functions:

- `retrieve -> construct -> render` references `publish_event` **zero** times
  (`tests/test_workflow_runner.py:599-607`, now `augment.augment_prompt` /
  `augment.default_retrieve_fn` / `augment.default_construct_fn`).
- The sole KB writer is the opt-in `emit_self` path, funneled through
  `emit_phase_finding` in `workflow_runner._emit_self_finding` (`:254-267`).

**PASS** — the isolation invariant holds across the split: the read side moved wholesale into
`augment.py`; the write side stayed in `workflow_runner.py`.

---

## 2. Docs refresh (restructure.md item 4)

### 2.1 `src/instrument/CONTEXT.md`

| # | Check | Result | Evidence |
|---|---|---|---|
| D1 | Module count corrected (was "40") | **PASS** | `:3` — "58 Python modules (+ `__init__.py`)" (matches the on-disk 58 non-`__init__` modules) |
| D2 | Five canonical-state producer modules named | **PASS** | `story_ingestion.py` (`:153`), `review_ingestion.py` (`:154`), `ledger_ingestion.py` (`:155`), `observation_ingestion.py` (`:156`), `actuation_ingestion.py` (`:157`) — each with `source_type`, authority/evidence class, and key exports |
| D3 | `message_family` / observation-vs-actuation | **PASS** | `knowledge.py` row documents `OBSERVATION_TYPES`/`ACTUATION_TYPES` + `message_family()` (`:145`); prose on the orthogonal split + the three `publish_event` gates (`:170-177`) |
| D4 | Registry / tombstone / compaction | **PASS** | `:179-185` — `kb-registry-v1` → `registry_index.jsonl`, `upsert`/`supersede`/`delete` (tombstone), `generate_manifest.py` compaction → manifest `registry` array + `lifecycle_state` |
| D5 | `workflow_runner`/`augment` rows | **PASS** | `workflow_runner.py` row updated (587 ln, phase execution + emit) `:98`; new `augment.py` row `:99` |
| D6 | `knowledge_stream.py` row added (transport + gates) | **PASS** | `:148` — `CONSUMER_GROUPS` incl. `kb-registry-v1`, `SOURCE_TYPE_INDEX_KEY`, the three gates |
| D7 | Full source_type vocabulary (was "four") | **PASS** | `:159-168` — nine `source_type` values across the authority ordering |

### 2.2 `.opencode/instructions/mental-model.md` KB section

| # | Check | Result | Evidence |
|---|---|---|---|
| D8 | `supersedes`/`causes` ledger fields documented | **PASS** | `knowledge.py` block `:183-184` (plus `operation` tombstone note `:185`) |
| D9 | Five producers added | **PASS** | `story_ingestion` (`:242-247`), `review_ingestion` (`:249-253`), `ledger_ingestion` (`:255-259`), `observation_ingestion` (`:261-265`), `actuation_ingestion` (`:267-270`) |
| D10 | `augment.py` + split `workflow_runner.py` | **PASS** | `augment.py` block `:272-277`; `workflow_runner.py — phase execution + the opt-in self-build emit` `:279-284` |
| D11 | One-typed-stream + write-time registration summary | **PASS** | `:297-300` — "nine source_type values", "ONE typed stream", write-time registration live in four call sites + `kb_produce*` + emit_self, "NOT only emit_self anymore" |
| D12 | Registry / tombstone / compaction | **PASS** | `:302-306` — `kb-registry-v1` → `registry_index.jsonl`, `generate_manifest.py` compaction, `scripts/registry.py` + `/api/registry*` |
| D13 | `message_family` gates + `kb-registry-v1` consumer | **PASS** | `:187` (`message_family`), `:200` (`CONSUMER_GROUPS` incl. `kb-registry-v1`), `:202-204` (three gates) |

---

## 3. Test result

| Gate | Command | Result |
|---|---|---|
| Required (spec VERIFY) | `pytest tests/test_workflow_runner.py tests/test_retrieval.py tests/test_prompt_constructor.py -q` | **111 passed** |
| Full suite | `pytest tests/ -m "not external" -q` | **1026 passed, 101 deselected, 0 failures** (19 pre-existing deprecation warnings) |

Behavior is unchanged: the augmentation path, the four fallback modes (`full` /
`lexical_graph_only` / `dense_local_exact` / `no_rag`), and the `PhaseResult` provenance fields
are byte-compatible — the workflow tests needed only their *import path* updated
(`default_retrieve_fn` now imported from `instrument.augment`, and the read-only-invariant test
now points at the moved functions), not their assertions.

---

## 4. Verdict

**PASS** on all checks.

- R7 is delivered: `augment.py` owns the `retrieve -> construct -> render` seam (pure, read-only,
  lazy optional deps); `workflow_runner.py` owns phase execution + the opt-in `emit_self` emit and
  calls out to `augment` — exactly the responsibility cut `restructure.md` R7 specified.
- The docs refresh closes `restructure.md` item 4: CONTEXT.md names all five canonical-state
  producers, documents `message_family`/observation-vs-actuation and the registry/tombstone/
  compaction machinery, and corrects the module count to 58; the mental-model KB section now lists
  `supersedes`/`causes` and the one-typed-stream + write-time-registration summary.
- The full suite is green with no test weakened or deleted.

One non-blocking note: the two workflow test *function names*
(`test_default_retrieve_fn_binds_dense_and_graph_stores`, `test_default_retrieve_fn_degrades_to_no_rag_when_stores_down`)
still carry the old `_default_retrieve_fn` spelling in their identifiers while the tested symbol is
now the public `default_retrieve_fn`. The tests import and call the correct symbol; the names are
cosmetic and were left unchanged to avoid weakening/renaming churn in a behavior-preservation phase.
