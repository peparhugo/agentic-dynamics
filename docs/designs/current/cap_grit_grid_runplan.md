---
status: accepted
---
# E4 cap_grit_strength_grid — run plan (x1_compile_and_setup)

Phase x1 of `cap_grit_grid_execute`: compile the spec, verify the 8-cell matrix, declare exact
per-cell run parameters from the spec's 9 findings, prepare the results-ledger skeleton, and
verify `CLAUDE_BIN` + backend resolution. **Flash orchestrates; cells run sonnet-5 via
`claude_cli`, SEQUENTIALLY.**

## 1. Compile + matrix check — PASS

`compile_spec(experiments/definitions/cap_grit_strength_grid.yaml)` → DAG
`validate → cells → execute → measure → compare → writeup → adapt` with feedback
`adapt → cells`. `validate_spec` returns **zero errors** (the requires/produces gate passes:
every `requires` is a real `LEDGER_FIELDS` member; all `requires_facts: []`).

`experiment_matrix(spec)` → **exactly 8 cells** = `condition_strength {clean, bad_seed_low,
bad_seed_mid, bad_seed_high} (4) × policy_arm {baseline, grit_retry} (2) × model
{anthropic/claude-sonnet-5} (1)`. GUARD met: 8 cells, no more.

## 2. Cell table — declared run parameters (per spec findings 1, 2, 4)

Story pinned to `task_manager_api` (BUILTIN_STORIES, python); seed codebase
`experiments/codebases/python/tier1_minimal/good` (the `bad` sibling at
`.../tier1_minimal/bad` is the standard BAD_SEED variant). All cells: `model =
anthropic/claude-sonnet-5`, `backend = claude_cli`, worktree under `/tmp`.

| # | cell (condition_strength × policy_arm) | condition | mutation artifact | strength | max_attempts | retry rule | est cost (USD) |
|---|---|---|---|---|---|---|---|
| 1 | clean × baseline | CLEAN | `None` | 0.0 | 1 | score single attempt unconditionally | 0.30–0.60 |
| 2 | clean × grit_retry | CLEAN | `None` | 0.0 | 2 | 2nd attempt only if 1st `test_executed_success=false` | 0.30–1.20 |
| 3 | bad_seed_low × baseline | BAD_SEED | `compile_mutation(bad_seed seam, s=0.2)` * | 0.2 | 1 | score single attempt unconditionally | 0.30–0.60 |
| 4 | bad_seed_low × grit_retry | BAD_SEED | `compile_mutation(bad_seed seam, s=0.2)` * | 0.2 | 2 | 2nd attempt only if 1st `test_executed_success=false` | 0.30–1.20 |
| 5 | bad_seed_mid × baseline | BAD_SEED | `None` (standard `CONDITION_STRENGTH=0.5` path) | 0.5 | 1 | score single attempt unconditionally | 0.30–0.60 |
| 6 | bad_seed_mid × grit_retry | BAD_SEED | `None` (standard `CONDITION_STRENGTH=0.5` path) | 0.5 | 2 | 2nd attempt only if 1st `test_executed_success=false` | 0.30–1.20 |
| 7 | bad_seed_high × baseline | BAD_SEED | `compile_mutation(bad_seed seam, s=0.8)` * | 0.8 | 1 | score single attempt unconditionally | 0.30–0.60 |
| 8 | bad_seed_high × grit_retry | BAD_SEED | `compile_mutation(bad_seed seam, s=0.8)` * | 0.8 | 2 | 2nd attempt only if 1st `test_executed_success=false` | 0.30–1.20 |

* Findings F1–F2 below: the `bad_seed` mutation seam is **not executable as written** in the
current code. Cells 3/4/7/8 are the ones the executor must resolve BEFORE running (x2), or
record as an accepted pilot limitation.

**Worst-case grid cost (finding 6):** 4 baseline × $0.60 + 4 grit_retry × $1.20 = **$7.20**,
under the `stop.budget_usd = $10.00` ceiling. Per-cell cost is logged before/after each run.

## 3. Findings — declared seam vs. verified code (honest, per workflow hard rule 3)

x1 verified every declared mechanism against real code rather than trusting the spec's prose.
Four discrepancies surfaced; they are **findings, not silent choices**:

- **F1 — `bad_seed` is not a compilable operator.** Spec finding 2 declares
  `compile_mutation(spec, "bad_seed", strength=0.2, ...)`. Verified:
  `"bad_seed" not in ALL_OPERATORS` (`measurement/mutation.py:51`) and
  `compile_mutation(..., operator="bad_seed", ...)` **raises `ValueError: Unknown operator`**
  (reproduced). The only place `operator="bad_seed"` exists is the label
  `condition_to_mutations` stamps on the pre-generated variant (`conditions.py:74`) — a label,
  not a registered compiler operator. There is no strength-parameterized `bad_seed` compiler.
- **F2 — the `run_story(mutation=...)` override is not wired to the worktree.** Spec finding 2
  calls it "run_story's own documented override seam" (`orchestration.py:50` docstring: "Optional
  explicit MutationArtifact (overrides condition)"). Verified: the `mutation` argument is used
  **only** as a gate (`if mutation is None and condition != CLEAN`, `orchestration.py:108`);
  the worktree is always fed `codebase_mutation` from `condition_to_mutations` (or `None`)
  (`orchestration.py:129-135`). The caller-supplied artifact is **never applied**. So supplying
  `mutation=<artifact>` today changes nothing on disk.
- **F3 — `perturbation_strength` is set from the condition, not the override.**
  `run_story` records `perturbation_strength = 0.0 if CLEAN else CONDITION_STRENGTH`
  (`orchestration.py:123`) regardless of any override strength. Even if a real s=0.2/0.8
  mutation existed and were applied, the `StoryResult` would still carry `0.5`. For
  `grit()` to see honest strength labels, the executor must patch
  `result.perturbation_strength` to the declared cell strength (0.2/0.8) AFTER the run — an
  explicit, documented step, never a silent coercion.
- **F4 — mechanical distinctness of the strength axis.** The standard BAD_SEED path (cells 5/6)
  uses one fixed pre-generated `bad` variant on disk; there is no low/mid/high variant set. With
  F1+F2, cells 3/4/7/8 currently resolve to the same mechanical degradation as 5/6 unless x2
  actually compiles and applies a real codebase mutation at the declared strength. This is a
  pilot-fidelity limitation to record (it compounds finding 5's under-power caveat), not a claim
  of three genuine strength manipulations.

**Resolution for x2:** either (a) wire F2 by passing the caller's mutation into
`_prepare_worktree` and use a real codebase operator (e.g. `inject_bug`) at s=0.2/0.8 —
a deviation from the spec's literal `bad_seed` operator name that MUST be recorded as a
finding in the x5 adversarial log; or (b) run cells 3/4/7/8 on the standard BAD_SEED path and
record the realized strength as 0.5 with an explicit fidelity note. **The executor must not
silently invent a third option.**

## 4. Backend + binary verification — PASS

- `get_backend_for_model("anthropic/claude-sonnet-5")` → **`claude_cli`** (provider `anthropic`
  routes to Claude CLI; `backends.py:27-28`). `resolve_backend(model, None)` and
  `resolve_backend(model, "claude_cli")` both → `claude_cli`.
- `CLAUDE_BIN=/home/drseuss/.local/bin/claude` (symlink → Claude Code **2.1.228**, verified
  `claude --version` runs). `claude_adapter.CLAUDE_BIN` resolves to the same value — the
  module const is read from `os.environ` at import (`claude_adapter.py:52`), so the cells'
  backend is executable as declared.
- Orphan note: `claude` is not on `PATH` in this shell; the cells rely on `CLAUDE_BIN` being
  exported. **x2 must confirm `CLAUDE_BIN` is set in the cell-runner environment**, or the
  adapter falls back to `shutil.which("claude")` → None → `"claude"` and fails.

## 5. Ledger skeleton — prepared

- `experiments/results/cap_grit_grid_ledger.json` — the grid ledger, **one entry per cell** (8),
  each carrying `cell_id`, `condition_strength`, `policy_arm`, `model`, `condition`,
  `mutation_artifact`, `strength`, `max_attempts`, `retry_rule`, `status: pending`, `attempts: []`.
  Attempt rows (populated by x2) must use the `LEDGER_FIELDS` vocabulary (`actual_cost`,
  `rework_cost`, `perturbation_strength`, `test_executed_success`, `policy_arm`,
  `attempt_number`, `parent_attempt_id`, `condition`, `strength`) — finding 3 of the spec.
- `experiments/results/stories/` — exists; x2 writes per-cell `task_manager_api_*_sonnet-5_*.json`
  via `save_story_result` (the naming pattern in `run_story.py:174`).

## 6. Handoff to x2

1. Resolve F1–F4 before running cells 3/4/7/8 (record the resolution as a finding).
2. Run cells SEQUENTIALLY in the table order; log realized cost before/after each; stop cleanly
   on Claude usage-cap errors (commit + resume), tracking against the $10 ceiling.
3. For grit_retry cells, implement finding 4's policy at the ledger level: if the first
   attempt's `test_executed_success` is false, queue a second attempt (`attempt_number=2`,
   `parent_attempt_id=<first>`) before scoring; baseline never retries.
4. Patch `perturbation_strength` per F3 for low/high cells; record the patch.
5. x3 measures the registered rules over the populated ledger; x5 re-verifies fidelity.

## 7. PASS/FAIL

- Compile gate: **PASS** (0 errors, DAG emitted).
- Matrix: **PASS** (exactly 8 cells, 4×2×1).
- Backend/binary: **PASS** (`claude_cli`, CLAUDE_BIN 2.1.228).
- Ledger skeleton: **PASS** (8-cell grid ledger + stories dir).
- Declared-seam verification: **PASS with findings** — F1–F4 recorded, no params invented.
- Overall: **PASS** (x1 complete; x2 blocked on F1/F2 resolution for the low/high cells).
