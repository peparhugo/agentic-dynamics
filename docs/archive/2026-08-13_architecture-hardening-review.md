---
status: superseded
superseded_by: ARCHITECTURE.md
---
# Agent Code Review — Architecture Hardening & Improvement

| Field | Value |
|---|---|
| **Reviewer** | opencode agent · `deepseek/deepseek-v4-pro` |
| **Date** | 2026-08-13 |
| **Repo** | `ai-finops-framework` (branch `main`) |
| **Scope** | `src/instrument/` (21 modules), `scripts/` (35 scripts), `admin/`, `conventions/`, `infrastructure/`, `.github/workflows/` |
| **Method** | Line-by-line read of the measurement chain (`perturb`, `solution`, `basin`, `strategy`, `mutation`, `commit_analysis`, `language`, `opencode`, `claude_adapter`, `routing`, `game_report`, `efficiency`, `story`, `streaming`, `live`, `backends`) and the data pipeline (`analyze_worktrees`, `build_data`, `run_story`, `pipeline`, `worker`, `enqueue`, `_constants`), cross-referenced against `mental-model.md`, `BLUEPRINT.md`, and `BLUEPRINT_v2.md`. |
| **Verdict** | Architecturally sound seams (backend dispatch, telemetry no-op, provenance discipline), but a measurement instrument that silently fabricates or mis-bills numbers on several paths. **P0 fixes required before trusting cross-model conclusions.** |

---

## Executive summary

The layering is genuinely good — `backends.py` gives a clean seam (`opencode`/`claude_cli` → `AgenticResult`), `live.py` degrades gracefully when Redis is down, and the [M]/[C]/[H]/[X] provenance discipline survived the corpus. The problems are not in the *shape* of the architecture but in the *quiet* failure modes: several code paths silently produce wrong numbers rather than crashing.

Three themes dominate:

1. **Data integrity.** Pricing constants exist in three places with conflicting values; `build_data.py` fabricates a 100% pass rate when `stories.parquet` exists; the mutation cache never writes; a failed mutation compilation silently turns a perturbed cell into a clean one.
2. **Dead taxonomy / drift.** The `semantic`/`manifold` split was replaced by a three-way taxonomy (`specification_corruption`/`objective_mutation`/`process_perturbation`), but `basin.get_verdict()` and `perturb.py` docstrings still branch on the old one. The website `external_sources` still emits the architecture constants the Phase 3.2 cleanup removed.
3. **Error-as-value.** Git/subprocess helpers return `"git error: …"` strings or empty strings that flow undetected into `commit_hash`, diff counts, and patch application.

Severity legend: **P0** corrupts measurements/claims · **P1** robustness & hardening · **P2** maintainability & drift.

---

## P0 — Measurement integrity (corrupts the science)

### P0-1. `build_data.py` fabricates a 100% pass rate

`scripts/build_data.py:779-841` (`compute_story_models`) is treated as "source of truth" and **replaces the entire `models` list** at `:864-867`, discarding the real correctness/energy/strategy/AST/Sonar metrics computed by `compute_model_data`. The replacement hardcodes:

- `:826` — `"tests_passed": row[12]` (comment: `# all stories passed`)
- `:829` — `"pass_rate": f"100% ({row[12]}/{row[12]})"` — passes **forced equal to total**
- `:830-837` — `narration_rate: 0`, `avg_energy_j: 0.0`, `strategy_*: 0`

The story pipeline does not re-run tests to verify correctness (BLUEPRINT_v2 lists "binary correctness metric" as a known limitation). The moment `experiments/data/stories.parquet` exists, the website's cross-model comparison shows invented numbers.

**Solution**
- Do not let `compute_story_models` override `models`. Either merge story-derived fields into the `compute_model_data` output, or keep the two under separate keys (`models` vs `story_models`).
- Emit real measured pass/fail by re-running `scripts/validate_session.py` in story worktrees, or emit `null` / `"unknown"` when correctness was not verified.
- Never set `tests_passed == tests_total` programmatically. Add a unit test that fails if any emitted `pass_rate` claims 100% without a corresponding measured test count.

### P0-2. Three conflicting pricing sources + a fourth hardcoded fallback

- `src/instrument/efficiency.py:41-85` — `PROVIDER_PRICING` (deepseek `0.435/0.87`)
- `scripts/_constants.py:21-47` — a second `PROVIDER_PRICING` (deepseek `0.27/1.10`), *also* claiming to be the historical billing snapshot
- `src/instrument/basin.py:230` — hardcoded `0.27/1.10/0.14` in the cost fallback

Two dicts with the same name and different numbers means a script's cost output depends on which import it happens to use.

**Solution**
- Create a single `src/instrument/pricing.py` with `HISTORICAL_PRICING` (dated snapshot) and `CURRENT_REFERENCE_PRICING`, each carrying an explicit `billing_date`.
- Make `efficiency`, `_constants`, `basin`, `claude_adapter._estimate_claude_cost`, and `build_data` all import from it.
- Delete `_constants.PROVIDER_PRICING`. Add `tests/test_pricing.py` asserting every pricing lookup resolves through one module (no literal rates anywhere else).

### P0-3. `build_data.py` resurrects the removed architecture constants

`scripts/build_data.py:1013-1014` emits `claude_active_params: 500B` and `deepseek_active_params: 37B` into `external_sources` with provenance `[X]`. These are the exact unverifiable constants removed in BLUEPRINT Phase 3.2 — `efficiency.py:23-25` now has `CLAUDE_EST_ACTIVE_PARAMS = None` and `_ENERGY_MODEL_AVAILABLE = False`, and `DEEPSEEK_ACTIVE_PARAMS` was corrected 37B→49B. The website data resurrects the debunked numbers.

**Solution**
- Remove `claude_active_params` and `deepseek_active_params` from `external_sources`.
- Emit `energy_model_available: false` (mirroring `efficiency.py:25`) and reference `49e9` if a DeepSeek figure is genuinely needed.

### P0-4. `strategy.py` absolute cost thresholds → cross-model bias

`src/instrument/strategy.py:140-142`:

```python
is_expensive  = thinking_ratio >= 0.6 or cost >= 0.01
is_efficient  = thinking_ratio <= 0.3 and cost <= 0.003
is_wasteful   = correctness <= 0.3 and cost >= 0.005
```

These are absolute USD thresholds. A `$0.01` task is trivially "expensive" for Claude ($3/$15 rates) and unreachable for DeepSeek ($0.435/$0.87). A DeepSeek run classified EFFICIENT and a Claude run classified WASTEFUL may reflect only the price gap, not strategy. This directly poisons the cross-model comparison that is the project's next goal.

**Solution**
- Replace absolute thresholds with model-relative ones: e.g. cost expressed as a ratio to that model's corpus median, or a per-provider `cost_scale` derived from the pricing snapshot. At minimum, parameterize and document the thresholds as `[H]` design parameters (they already appear as design parameters in `build_data.py:997-1001` but are not wired to `classify_strategy`).
- Add a test asserting classification is invariant under a uniform price rescaling.

### P0-5. Dead taxonomy: `basin.get_verdict()` branches on `semantic`/`manifold`

`src/instrument/basin.py:82-90` checks `c == "semantic"` and treats the else-branch as `"manifold"`. But `build_operators()` (`perturb.py:601-661`) now assigns `specification_corruption` / `objective_mutation` / `process_perturbation`. Every run falls through to the "manifold" verdict (*"escaped — expected for manifold class"*) — a class that no longer exists. Related drift:

- `perturb.py:87` — `Perturbation.perturbation_class` default is still `"semantic"`.
- `perturb.py:5, 117-118` and operator descriptions still use "manifold"/"latent-space navigation" language.

**Solution**
- Rewrite `get_verdict()` against the three-way taxonomy; map each class to an expected-divergence semantic explicitly.
- Change the `Perturbation` default to `""` (unknown) or `"process_perturbation"`.
- Purge "manifold"/"latent space" prose from `perturb.py` docstrings (mirrors the Phase 4.5 cleanup done elsewhere).

### P0-6. The mutation cache never writes

`src/instrument/mutation.py:222-225` checks `cache_path.exists()` and returns the cached artifact, but neither `compile_mutation` nor `_compile_spec_mutation` / `_compile_codebase_mutation` ever calls `artifact.save(cache_path)`. The cache is read-only dead code: every BAD_SEED / EARLY_DEGRADE run re-invokes Flash V4 (time + cost) and, worse, gets a *different* mutation each time because there's no pinned write.

**Solution**
- Save the artifact after compilation, once, in `compile_mutation` (after `_compile_spec_mutation` / `_compile_codebase_mutation` return), before returning.
- Add a test: compile twice with the same inputs and assert the second call hits the cache (no second subprocess).

### P0-7. Failed mutation compilation silently produces a clean cell

`src/instrument/mutation.py:254` — `artifact.mutated_spec = mutated or specification`. If `_call_opencode` returns `None` (timeout, spawn failure), the "mutated" spec is byte-identical to the original, but the run proceeds and is recorded as a mutation. A transient Flash failure silently converts a perturbation condition into a clean control run — undetectable downstream.

**Solution**
- On `None`/empty, raise `ValueError("mutation compilation failed")` (or mark `noop_reason="compiler_failed"` and let `run_story` abort). Do not silently fall back to the clean spec.
- Surface compiler failure in the `StoryResult.error` field.

### P0-8. Baseline matching can cross-contaminate across tasks

`scripts/analyze_worktrees.py:1002-1011` (Priority 4) falls back to *"any baseline for the same model/provider"* — so a perturbed `url_shortener` run with no baseline is compared against a `task_manager` baseline, producing basin-escape numbers recorded as valid. Priority 1's fingerprint threshold `> 0.25` (`:978`) is loose enough to match a different experiment.

**Solution**
- Drop Priority 4 (cross-experiment fallback) or require `experiment` equality.
- Record *which* baseline matched and a confidence in the metrics dict, so downstream consumers can flag low-confidence matches.
- Raise the fingerprint threshold and log it.

### P0-9. Convention scoring ignores 45% of the declared rubric

`scripts/../src/instrument/commit_analysis.py:351-352` reads only `naming_weight` and `structure_weight`, and applies `structure_weight` to `forbidden_patterns` (which are *naming* anti-patterns). The `conventions/python.yaml` and `conventions/typescript.yaml` `scoring:` blocks declare `documentation_weight` and `type_safety_weight` (docstrings, import order, type hints, line length, module docstrings) — **none of which are ever evaluated**. The declared 4-way rubric computes as a 2-way one, and the TS convention artifact BLUEPRINT_v2 flagged is only half-fixed.

**Solution**
- Either implement the missing checks (docstring presence, import order, type hints, line length) or **remove the un-computed weights from the YAML** so the rubric matches reality.
- Use the correct weight key per category (`forbidden_patterns` belongs under naming, not structure).

### P0-10. "AST diff" is regex, not AST, and miscounts Go/Rust

`src/instrument/commit_analysis.py:276-293` regexes `+def `/`+class `/`+import ` on raw `git diff` hunks — `language.py`'s tree-sitter machinery is bypassed entirely. The non-Python branch only matches `+function `/`+class `/`+import `, so Go (`func `) and Rust (`fn `) count **zero** functions/classes/imports. Despite `language.py` claiming 4-language support, the diff layer is really Python+TS only.

**Solution**
- Either count structural elements with tree-sitter at both commits, or add Go/Rust patterns (`func `, `fn `, `type `, `use `) to the regex branch and rename the function to reflect that it is a diff-stat heuristic, not an AST diff.
- Add `tests/test_commit_analysis.py` cases for Go and Rust samples.

### P0-11. `game_report.py` overstates test independence

`src/instrument/game_report.py:160` renders correctness `[M]` (measured) whenever `tests_total > 0`, but the instrument's own accounting sets `evaluator_independent = False` (tests are agent-authored). This is the same overclaim Phase 1 was meant to fix.

**Solution**
- Use `solution.evaluator_source` / `evaluator_independent` to choose the tag: `[M]` only when independent, otherwise `[H]` (or a new `[M-agent]` tag) with the caveat surfaced.

### P0-12. `run_pytest` excludes errors from the total

`scripts/analyze_worktrees.py:98-107` parses `passed`, `failed`, and `errors`, but sets `total = passed + failed`. If pytest reports `5 passed, 0 failed, 3 errors`, `total == 5`, `pass_rate == 1.0` while `ok` is `False`. The 3 errored collections vanish from the denominator.

**Solution**
- `total = passed + failed + errors`; `correctness = passed / max(total, 1)`.
- Assert in a test that an errored run can never report 100%.

---

## P1 — Robustness & hardening

### P1-1. `stream_subprocess` kills only the child, not the process group

`src/instrument/streaming.py:88-90` calls `proc.kill()` on timeout — opencode-spawned test runners / build tools get orphaned. The 5s reader-thread joins (`:93-94`) can also leave dangling threads holding the pipe.

**Solution**
- `Popen(..., start_new_session=True)`; on timeout `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` then `proc.wait()`.
- Join reader threads without a fixed deadline (they end when the pipe closes), or drain the pipe explicitly.

### P1-2. Error-as-value across the git/subprocess boundary

- `src/instrument/story.py:867-879` — `_git` returns `f"git error: {e}"`; `:721` feeds it straight into `commit_hash` → a bogus hash lands in results JSON.
- `src/instrument/commit_analysis.py:619-630` — `_run_git` returns `""` on failure → zero counts recorded as "no change".
- `src/instrument/mutation.py:404-409` — `patch` runs with `check=False`; a failed patch is silently ignored and the caller proceeds as if mutated. `apply_mutation` also returns `None` despite `mental-model.md` documenting `apply_mutation(artifact, target_path) -> bool`.

**Solution**
- Make `_git` / `_run_git` raise on non-zero exit (or return a typed `(code, stdout)` tuple). Never return error text through a value channel.
- `apply_mutation`: check the patch return code and return `bool`; verify the mutation actually changed the target.

### P1-3. opencode SQLite schema coupling with no version check

`scripts/analyze_worktrees.py:214-216` and `scripts/build_data.py:149` depend on `json_extract(model,'$.providerID')` / `'$.id'` and `directory LIKE '.../exp_%'`. A schema change silently yields zero sessions / zero tokens with no error.

**Solution**
- Add a startup probe (e.g. `PRAGMA table_info(session)`, or a trivial `SELECT json_extract(...) LIMIT 1`) and fail loudly if the expected shape is absent.

### P1-4. Pipeline control-path errors are swallowed

- `scripts/pipeline.py:285-291, 1019-1023` — `_set_state` / `_set_current` catch-and-`pass` Redis failures, so phase transitions are lost silently.
- `:1094` — `while not executor(phase, context): time.sleep(30)` polls forever with no stall/timeout watchdog.
- `:304-316` — `_spawn_workers` uses `nohup` with no PID tracking; `scripts/worker.py` has no signal handler → orphan workers after Ctrl-C.

**Solution**
- Log (or raise) on Redis state-write failures — telemetry may no-op, state must not.
- Add a max-wall-clock / stale-worker watchdog to the polling loop.
- Track worker PIDs in a sidecar; add SIGTERM/SIGINT handling in `worker.py` to mark the in-flight cell `failed`.

### P1-5. Inconsistent runtime configuration

- `src/instrument/story.py:666` hardcodes `Path.home()/".opencode/bin/opencode"` while `opencode.py` and `mutation.py` honor `OPENCODE_BIN`.
- Timeout mismatch: `worker.py:140` passes `--timeout 900`, `run_story.py:83` defaults 1200, `worker.py:29` kills at 9000.
- `PerturbationCondition.LATE_DEGRADE` is defined (`story.py:49`) and handled (`condition_to_mutations`) but **not exposed** in `run_story.py:78` CLI choices.
- Slug logic differs (`run_story.py:167` vs `enqueue.py:52-56`) → cross-script filename collision risk.

**Solution**
- Single `resolve_opencode_bin()` helper shared by all three modules.
- Single `SESSION_TIMEOUT` constant; derive worker kill timeout from it (e.g. `TIMEOUT_PER_CELL = n_sessions * session_timeout * margin`).
- Add `late_degrade` to `run_story.py` choices; unify `model_slug()` in `_constants.py`.

---

## P2 — Maintainability & drift

### P2-1. ~30 deprecated re-exports + stale artifacts + dual orchestration

`src/instrument/__init__.py` re-exports `adapter`, `experiment`, `lab_book`, `trajectory`, `recovery`, `constraint_detection`, `semantic_validation`, `embeddings`, `graph`, `ollama_analyzer`, `sonar` — many of which pull optional heavy deps (chromadb/neo4j/ollama) and are deprecated. `src/reasoning_instrument.egg-info/` survives the rename. `scripts/plan.py` (549L) coexists with `pipeline.py` (1255L); two review runners (`review_all.py` vs `review_stories.py`+`review_worker.py`).

**Solution**
- Delete `adapter.py` / `experiment.py` / `lab_book.py` and remove their exports.
- Move optional-dep modules (`graph`, `embeddings`, `ollama_analyzer`) behind lazy import or `instrument.extras`.
- Delete the stale egg-info; retire `plan.py` and `review_worker.py`.

### P2-2. `build_data.py` is a 1063-line god script

- `_load_review_data` / `_load_analysis_data` / `_load_story_data` each re-derive `sid_to_model` via `f.stem.split("_")[-1]` + `len(sid)>=8` (three copies).
- `compute_calculator:353` and `compute_derived:392-409` parse `pass_rate` by string-splitting a formatted `"100% (5/5) [tests]"`.
- `:966-967` hardcode `architectures: 3`, `variants: 8`.

**Solution**
- Extract story-id→model resolution and pass-rate parsing into typed helpers.
- Compute `architectures`/`variants` from data, not literals.

### P2-3. Composite weights duplicated 4×

`0.35/0.30/0.20/0.15` (and the Sonar `0.30/0.25/0.20/0.15/0.10`) appear in `solution.py:161-166`, `analyze_worktrees.py:474-478` and `:582-595`, and `build_data.py:1002-1005`.

**Solution**
- Single `COMPOSITE_WEIGHTS` constant in one module; reference it everywhere.

### P2-4. Repo hygiene & CI

- 137 untracked `experiments/results/analysis/analysis_*.json` files flood `git status` (`.gitignore` never covers that dir).
- `.github/workflows/pytest.yml` references `tests/test_value_score.py`, which **does not exist** → the pytest step fails. It also runs a hardcoded subset, so `test_pipeline.py`, `test_backends.py`, `test_streaming.py`, etc. never run in CI.

**Solution**
- Add `experiments/results/analysis/` (or the whole generated-results tree) to `.gitignore`.
- Fix the CI test list to match reality and run the full `pytest tests/`; add `ruff` + `mypy` to CI.

### P2-5. Schema validation absent on external input

`src/instrument/story.py:150` (`SessionSpec.from_dict` → `d["session_number"]`) and `scripts/pipeline.py:136-137` (`_parse_phase` → `p["id"]`, `p["kind"]`) do bare key reads → `KeyError` on malformed YAML/JSON.

**Solution**
- `.get()` with defaults + explicit validation of required fields, raising actionable errors.

### P2-6. `rm -rf /tmp/exp_*` only "ask"

`opencode.json` sets `rm -rf /tmp/exp_*` to `ask`, but `/tmp` is the live worktree root.

**Solution**
- Scope that permission to an explicit cleanup script (allowlist) rather than a raw glob.

---

## Cross-cutting recommendations

1. **Single source of truth for pricing** (P0-2, P0-3) — one module, dated snapshots, no literals elsewhere.
2. **Provenance must match reality** (P0-1, P0-11) — never emit a measured tag for an unmeasured or agent-authored quantity.
3. **Fail loudly, not silently** (P0-7, P1-2, P1-3, P1-4) — the instrument's value is in *not* inventing data; silent fallbacks are the worst failure mode for a measurement tool.
4. **Test coverage for `scripts/`** — the P0 correctness logic (baseline matching, pass-rate aggregation, pricing resolution) lives in the least-tested layer. Only `tests/test_pipeline.py` exercises `scripts/` today.
5. **Pin the taxonomy** — one enum for `perturbation_class` consumed everywhere (P0-5), so renaming a class can't leave dead branches behind.

---

## Prioritized remediation plan

| Phase | Items | Rationale |
|---|---|---|
| **1 — Data integrity** (do first) | P0-1, P0-2, P0-3, P0-6, P0-7 | Fabricated/re-billed numbers block every downstream conclusion. |
| **2 — Taxonomy & thresholds** | P0-4, P0-5 | Unblocks valid cross-model comparison. |
| **3 — Analysis correctness** | P0-8, P0-9, P0-10, P0-11, P0-12 | Fixes the correctness pipeline for Go/Rust/TS and conventions. |
| **4 — Robustness** | P1-1 … P1-5 | Process groups, error-as-value, schema probe, watchdog, config unification. |
| **5 — Cleanup** | P2-1 … P2-6 | Deprecated surface, god-script extraction, CI, gitignore. |

## Appendix — full reference index

| Finding | Location |
|---|---|
| P0-1 fabricated pass rate | `scripts/build_data.py:826,829,830-837,864-867` |
| P0-2 pricing conflict | `efficiency.py:41-85` · `_constants.py:21-47` · `basin.py:230` |
| P0-3 resurrected arch constants | `scripts/build_data.py:1013-1014` |
| P0-4 absolute cost thresholds | `strategy.py:140-142` |
| P0-5 dead taxonomy | `basin.py:82-90` · `perturb.py:87,117-118` |
| P0-6 cache never writes | `mutation.py:222-225` |
| P0-7 silent clean cell | `mutation.py:254` |
| P0-8 baseline contamination | `analyze_worktrees.py:978,1002-1011` |
| P0-9 convention rubric gap | `commit_analysis.py:351-352` + `conventions/*.yaml` |
| P0-10 regex "AST" diff | `commit_analysis.py:276-293` |
| P0-11 [M] overclaim | `game_report.py:160` |
| P0-12 errors excluded from total | `analyze_worktrees.py:98-107` |
| P1-1 no process-group kill | `streaming.py:88-94` |
| P1-2 error-as-value | `story.py:867-879,721` · `commit_analysis.py:619-630` · `mutation.py:404-409` |
| P1-3 schema coupling | `analyze_worktrees.py:214-216` · `build_data.py:149` |
| P1-4 swallowed control state | `pipeline.py:285-291,1019-1023,1094,304-316` · `worker.py` |
| P1-5 config inconsistency | `story.py:666` · `worker.py:29,140` · `run_story.py:78,83,167` |
| P2-1 deprecated surface | `src/instrument/__init__.py` · `src/*.egg-info/` · `plan.py` |
| P2-2 god script | `build_data.py` (1063L) |
| P2-3 duplicated weights | `solution.py:161-166` · `analyze_worktrees.py:474-478,582-595` · `build_data.py:1002-1005` |
| P2-4 hygiene/CI | `.gitignore` · `.github/workflows/pytest.yml` |
| P2-5 schema validation | `story.py:150` · `pipeline.py:136-137` |
| P2-6 permission scope | `opencode.json` |
