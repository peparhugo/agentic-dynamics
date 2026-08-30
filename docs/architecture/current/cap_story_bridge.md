---
status: accepted
---
# CAP Story Bridge — Token-Split Instrumentation + `story_facts/v1`

**Spec:** `workflows/repository/cap_story_bridge.yaml` (phases `s1_token_split_instrumentation`,
`s2_story_facts_reducer`, `s3_document`)
**Branch:** `feature/cap-story-bridge`
**Date:** 2026-08-25 · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Close the two story-family measurement gaps the backfill census named: (1) record
per-session token in/out splits so `attempt_tokens_in/out` become PRODUCED for stories, and (2)
implement the formal `story_facts/v1` reducer — a first-class fact-plane bridge consuming
`StoryResult` artifacts — so story-cell attempts become real predicates instead of
ledger-adaptation-only.

**Planned sections:** §1 s1 instrumentation (token split) · §2 the `story_facts/v1` reducer ·
§3 which predicates story attempts now produce · §4 what this unlocks · §5 what remains · §6
verification + PASS/FAIL.

---

## 1. s1 — story sessions record the backend-reported token split (instrumentation)

**Instrumented, additive, coverage-honest.** The story session recording now captures
`tokens.in`/`tokens.out` whenever the backend reports usage (opencode step_finish / claude usage),
*alongside* the existing flat `total_tokens` — never replacing it.

| File | Change |
|---|---|
| `src/agentic_dynamics/adapters/opencode.py:81` | `AgenticResult.usage_reported: bool` — set by `_parse_session_output` (`opencode.py:571`) on a real step_finish tokens dict, so a measured **zero** is distinguishable from **absent** (the null-safety fix the I2 gate depends on). |
| `src/agentic_dynamics/runtime/story/models.py:119` | `SessionResult.tokens: dict[str, int] \| None` — the backend-reported split, additive to `total_tokens`; `None` = coverage-not-available (flat total remains the valid fallback). |
| `src/agentic_dynamics/runtime/story/models.py:171` | `session_token_split(agentic)` — the single mapping: `None` when `usage_reported` is false (never fabricates a split); `{"in", "out"}` otherwise, including a measured `{0, 0}`. |
| `src/agentic_dynamics/runtime/story/models.py:145` | `SessionResult.to_dict()` omits `tokens` when `None` (absent stays absent on disk). |
| `src/agentic_dynamics/runtime/story/orchestration.py:418` | `_run_session` wires `tokens=session_token_split(agentic)` from the primary agentic result. |
| `src/agentic_dynamics/runtime/story/persistence.py:259` | `load_story_result` round-trips the split; a non-dict/absent `tokens` loads as `None`. |

**GUARD (s1): no semantic change when splits are absent.** A session with no `tokens` key
round-trips to `None`, serializes without the key, and behaves exactly as before — the 227 on-disk
cells that predate the instrumentation re-derive byte-identically (verified in the s1 commit log:
"227 on-disk cells carry no split → projections byte-identical"). `session_token_split` returns
`None` for any backend that never reported usage, so coverage-not-available is explicit, never a
fabricated `{0, 0}`.

**VERIFY (s1):** hermetic tests in `tests/test_story.py` (split present/absent, measured-zero,
serialization, save/load round-trip) + `tests/test_kb_produce_facts_extension.py`
(`test_story_token_split_becomes_produced`: the census's PARTIAL `attempt_tokens_in/out` story rows
become PRODUCED on re-derivation through the existing projection; stable ids; convergence). 57
story+extension+ledger tests passed at s1.

## 2. s2 — the `story_facts/v1` reducer (first-class story fact bridge)

The E4 writeup's gap (`experiments/definitions/cap_grit_strength_grid.yaml`, finding 3 — checked,
not assumed): `phase_test_verified`'s only producer was `attempt_facts/v1`, which consumes
`workflow_run` — **no registered reducer consumed `StoryResult`**. The p3 backfill bridged stories
through *ledger-adaptation* (producer-side projection of story sessions onto the `workflow_run`
shape, fed to the unchanged `attempt_facts/v1`). `story_facts/v1` is the formal reducer.

### 2.1 Declaration

`src/agentic_dynamics/control/reducers/story_facts.py`:

```
STORY_FACTS_V1 = ReducerSpec(
    name="story_facts", version="story_facts/v1",
    level="fact", scope_type="attempt",
    consumes=("story",),                    # the raw StoryResult artifact (source_type="story")
    produces=(phase_status, phase_commit, attempt_model, attempt_tokens_in, attempt_tokens_out,
              attempt_cost_usd, attempt_confidence, phase_test_verified),
    determinism="pure",
)
```

Registered in `REDUCERS` (`control/reducers/__init__.py`) + `__all__`; `get_reducer("story_facts/v1")`
resolves; `scripts/kb_produce_facts.py --reducer story_facts/v1` runs it over
`experiments/results/stories/*.json` (evidence family `_story_cell_evidence`,
`derive_story_facts_v1`). Each of the eight predicates now declares `story_facts/v1` in its
`FACT_PREDICATES.produced_by` tuple (`control/facts.py`) — additive, nothing removed.

### 2.2 Identity (evidence-identity + null-not-zero, verbatim from `attempt_facts/v1`)

- **Cell** = `wf_<story>_<condition>_<model>` (`_common.cell_id`); a condition that is empty or
  `"None"` is absent, so the 9 condition-less legacy cells land in the story's unconditioned cell.
- **Attempt** = `attempt:<session>` under `job:<cell>`, further run-qualified:
  `scope_id = <cell>:sessionN:<run_artifact_id>`. The run artifact is built by `_session_run`,
  which replicates `kb_produce_facts._project_story_session` **byte-for-byte**, so a
  `story_facts/v1` fact occupies the SAME logical slot the p3 adaptation derived under
  `attempt_facts/v1` — emission under the new reducer therefore **supersedes** the adaptation facts
  (same `fact_entity_id`, new `reducer_version`, registry supersede chain), never coexists with
  them as a conflicted second producer (proven by
  `tests/test_story_facts_reducer.py::test_producer_story_facts_v1_supersedes_the_projection_slot`).
- **Time-invariance / per-run identity:** entity_id is keyed by (repo, scope_id, subject,
  predicate) — never the injected clock; two distinct cells (different condition, or same cell with
  different recorded `started_at`) never collide; re-derivation over the same artifact is
  byte-identical (`test_rederivation_is_byte_identical_and_time_invariant`,
  `test_two_distinct_cells_never_collide_on_attempt_entity_id`).
- **Epistemics** are a pure function of the predicate (design §3.4): measured fields →
  `observed`/[M]; `attempt_confidence` → `advisory`/[H] (a self-report, `is_canonical` refuses it);
  `phase_test_verified` → `verified`/[M] (`StoryResult.test_executed_success` is documented
  "independently verified (test_runner), never self-report").

### 2.3 The two story-specific additions

1. **`phase_test_verified` — the test_executed_success-analogue.** Story cells record
   `test_executed_success` **cell-level only** (92/227 per the census); there is no per-session
   verdict to fabricate. The reducer attaches the cell's independent test outcome to the cell's
   **terminal** session attempt — the settled state the suite actually verified — and only when the
   field is a real `bool` (`None` → absent, null-not-zero; the 135/227 un-verified cells stay
   absent, never a fabricated `"false"`). Documented in the reducer's module docstring.
2. **`attempt_tokens_in`/`attempt_tokens_out` from the backend-reported split** — the s1
   instrumentation (additive to flat `total_tokens`); the null-safe gate emits them only where a
   backend reported a (possibly zero) value.

## 3. Which predicates story attempts now produce

| Predicate | Source field | Story coverage before | Story coverage after (with story_facts/v1) |
|---|---|---|---|
| `phase_status` | session `exit_code` / `error` | PRODUCED (projection) | PRODUCED (first-class) |
| `phase_commit` | session `commit_hash` (emit-gated non-empty) | 1111/1112 (projection) | 1111/1112 (first-class) |
| `attempt_model` | cell `model` | PRODUCED | PRODUCED |
| `attempt_cost_usd` | session `cost_usd` | PRODUCED | PRODUCED |
| `attempt_confidence` | session `confidence` (emit-gated non-None) | 401/1112 = 36% | 401/1112 = 36% — same measurement, now first-class |
| `attempt_tokens_in` / `attempt_tokens_out` | session `tokens` (s1, emit-gated non-None) | **0/1112 PARTIAL** | **wherever a backend reported a split** — the census's PARTIAL rows become PRODUCED on re-derivation |
| `phase_test_verified` | cell `test_executed_success` (emit-gated bool, terminal session) | 0 (no producer) | **92/227 cells** emit on their terminal session |

Job-level story facts (`job_status`, `job_accumulated_cost_usd`, `job_n_phases`, `current_commit`)
remain with `job_facts/v1` — all 227/227 PRODUCED since the p3 backfill (census §3b). **Why not
re-emit them here:** `verify_chain` requires `fact.abstraction_level == reducer_spec.level`, and a
single registered version cannot span attempt (`"fact"`) and job (`"job"`) levels; re-emitting job
facts under a second reducer_version would hand the registry two producers for one slot. The bridge
is the attempt-level first-class producer; job facts keep their single producer.

## 4. What this unlocks

**Story-cell control arms become writable via `requires_facts`.** The `compile_experiment`/
`context_compiler` gate validates `requires_facts` against `FACT_PREDICATES` (the real registry,
`context_compiler.py:998`) and resolves them against the decision's scope path
(`resolve_requirement_scope`, `context_compiler.py:206`). Before this work, E4's `grit` arm was
forced onto the **legacy** `requires:` mechanism because "no reducer anywhere bridges a story-cell
attempt into the CAP fact plane" (finding 3, verbatim) — `requires_facts` for `phase_test_verified`
/ `attempt_confidence` / `attempt_tokens_in/out` / `attempt_cost_usd` on a story cell was a
requirement with no honest predicate mapping. Now:

- **Confidence arms** (`model_cascade` / `dynamics`-family rules) can bind
  `requires_facts: [attempt_confidence]` for story cells — the per-session confidence the census
  counted (36%) is a real fact-plane predicate, ADVISORY/[H] like every other confidence fact.
- **Cost/verified-outcome arms** (E4's `grit`, `cost_per_verified_outcome`, `verified_success_rate`)
  can bind `requires_facts: [attempt_cost_usd, phase_test_verified]` — the test_executed_success
  analogue now exists at the fact plane for stories.
- **Coverage stays honest:** `perturbation_strength` still has **no** `FACT_PREDICATES` entry (it
  lives only in the legacy `LEDGER_FIELDS`), so E4's `perturbation_strength` requirement must keep
  the legacy `requires:` binding; a fact-plane producer for perturbation strength is a forward
  instrumentation step, not claimed here.

## 5. What remains

- **`phase_test_verified` for agent phases stays PARTIAL** (7/455). Agent phases in workflow runs
  stamp `test_executed_success: None` — the independent test-runner wiring for agent phases is the
  separate `cap_test_runner_wiring` stream, not this bridge.
- **Story cell-level confidence is measured, not universal** (401/1112, 36%); `story_facts/v1`
  emits what the cell recorded and nothing more.
- **`attempt_cache_hit_rate` for story sessions** stays absent — story sessions record no per-session
  cache field; the cell-level rollup is a job-summary value, not an attempt measurement.
- The p3 **projection** path (`derive_story_facts`, `--corpus story`) is intentionally unchanged;
  `story_facts/v1` is available as `--reducer story_facts/v1` (and `derive_story_facts_v1`). Moving
  the corpus emission wholesale from projection to bridge is an operator decision (it supersedes the
  projection's per-session facts cleanly — §2.2).

## 6. Verification + PASS/FAIL

**PASS (s2):**

| Guard / Verify | Evidence |
|---|---|
| Zero diffs to existing reducers | `git diff --stat src/agentic_dynamics/control/reducers/` = `__init__.py` (+5, registration) + the new `story_facts.py`; `attempt_facts.py`, `job_facts.py`, `workflow_facts.py`, `spec_status.py`, `policy_facts.py`, `_common.py`, `pattern.py`, `checkpoint.py` byte-identical. |
| Predicate vocabulary FACT_PREDICATES-only | `STORY_FACTS_V1.produces` ⊆ `FACT_PREDICATES`; asserted in `test_story_facts_reducer_is_registered`. |
| Hermetic tests | `tests/test_story_facts_reducer.py` — **14 passed**: registration; per-session attempt facts; job+run-qualified scope; epistemics; absent-fields-stay-absent; measured-zero vs absent split; `phase_test_verified` None-absent; failed-session status; byte-identical re-derivation + time-invariance; per-cell collision; `verify_chain` clean for every emitted fact; real `StoryResult` object consumption; producer-path convergence + supersede-the-projection-slot. |
| CAP suites + guards green | 331 (fact/context/knowledge/producer/story/ledger + guards) + 278 (compiler/contracts/controller/seam/actuation/fact-auto-emit/knowledge) + 501 adjacent — all green. Pre-existing drift failures (`test_lab_contract`, `test_lab_outputs_canonical`, `test_build_data`, `test_sync_data`) reproduce on the base commit unchanged; `test_ollama_analyzer`/`test_opencode_analyzer` hang on live-LLM subprocesses (environmental, untouched). |

**PASS/FAIL log:** s1 PASS (token-split instrumentation, additive, absent stays absent) · s2 PASS
(`story_facts/v1` registered + wired + hermetic) · s3 PASS (this document). Every claim above
traces to code (`story_facts.py`, `facts.py`, `kb_produce_facts.py`) or a named test
(`tests/test_story_facts_reducer.py`, `tests/test_story.py`,
`tests/test_kb_produce_facts_extension.py`). Branch: `feature/cap-story-bridge`; each phase commits
`[workflow] <phase>`.
