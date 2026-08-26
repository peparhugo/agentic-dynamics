---
status: accepted
---

# Null-not-zero ratio sweep — the `= 0.0`-when-denominator-missing guard

Part of `cap_stabilization_release` p1 (`workflows/repository/cap_stabilization_release.yaml`,
current_state item 7). The finding-economics closure removed `max(cost, tiny)` ratio floors from
the published corpus and the strategy report; this sweep verifies the strategy-plane items are
None (already fixed) and hunts the REMAINING same-class sites in the measurement/reporting
planes.

**Doctrine (unchanged):** a ratio whose denominator is uncaptured is `None` ("unavailable"),
never a fabricated `0.0` nor a `max(denom, tiny)` superspike. `to_dict()` round-trips it as JSON
`null` so no downstream reader can mistake an unmeasured ratio for a measured zero.

## Verified, no change

| Site | Disposition |
|---|---|
| `measurement/strategy.py:66-67` `exploration_premium` / `thermal_efficiency` | **Already fixed** — `float \| None = None`; guarded by `if cost > 0` / `if energy > 0`; `tests/test_strategy.py::test_economic_ratios_null_when_denominator_uncaptured` proves it. Verify-only per the spec. |
| `measurement/codebase_graph.py:175,176,348` `else 0.0` | **Not an offender** — graph-structural properties (density of a ≤1-node graph, avg degree of an empty graph, intra-dir fraction of an empty graph). The graph is fully measured; `0.0` is the mathematically standard value, not a coverage fabrication. |
| `reporting/measurement_coverage.py:93` `if n_total else 0.0` | **Not an offender** — the documented coverage convention (`0.0` coverage = 0% of rows priced). Deliberate, asserted by `tests/test_strategy.py` consumers. |
| `measurement/efficiency.py:349-350`, `basin.py:234` `thinking_ratio = reasoning / max(total, 1)` | **Not an offender** — when `total_tokens == 0` then `reasoning_tokens == 0` too, so `0/1 == 0.0` is the correct limit, not a fabrication. |
| `measurement/entropy.py` `return 0.0` guards | **Not an offender** — entropy of a constant/empty distribution is mathematically 0. |
| `reporting/review.py` score clamps | **Not an offender** — `max(0.0, min(1.0, score))` bounds a computed score, not a denominator-missing ratio. |

## Findings — same class as the already-fixed strategy.py items

Each of these computed a ratio against a possibly-zero denominator via `max(denom, tiny)` (a
superspike) or `max(denom, 1)` (a fabricated zero). All are now None-guarded.

| Site (before) | Fabricated output when denominator missing | Fix |
|---|---|---|
| `measurement/efficiency.py:369-372` `solution_density` / `correctness_per_dollar` / `quality_per_joule` / `efficiency_score` | `LOC / max(tokens,1)` → 0.0 or LOC; `correctness / max(cost, 1e-6)` → huge | None unless `total_tokens`/`total_cost_usd`/`total_energy_j` > 0 |
| `measurement/basin.py:255-257` `correctness_ratio` / `quality_per_dollar` / `quality_per_joule` | `perturbed / max(baseline, 0.01)` → 100× superspike on a 0-correctness baseline | None unless `baseline_correctness`/`cost_usd`/`estimated_energy_j` > 0 |
| `measurement/recovery_cost.py:149-150` `recovery_token_ratio` / `recovery_cost_ratio` | `0 / max(perturbed, 1)` → 0.0; `0 / max(cost, 1e-6)` → 0.0 | None unless `perturbed_tokens`/`perturbed_cost_usd` > 0 |
| `measurement/constraint_detection.py:158` `detection_rate` | `0 / max(0, 1)` → 0.0 ("detected none of none") | None unless `constraints_total` > 0 |

All four modules now carry `float | None` fields defaulting to `None`, and their `to_dict()`
round-trips `None` (no `round(None)` crash).

## Consumer updates

| File | Change |
|---|---|
| `reporting/game_report.py:140-141, 242-244` | Markdown renders `n/a (… uncaptured)` when a ratio is None instead of formatting 0.0. |
| `scripts/sweep_silent_mode.py:207` | Recovery-ratio line prints `n/a` when None instead of `0.00x`. |

`scripts/analyze_worktrees.py:729-731` and `knowledge/graph.py:367-421` pass the values through
unchanged — a None ratio already serializes as JSON `null` (coverage-correct).

## Guard tests

`tests/test_ratio_null_not_zero.py` (new) — 6 tests locking the null-not-zero shape per module,
mirroring `tests/test_strategy.py::test_economic_ratios_null_when_denominator_uncaptured`.
All 12 (6 new + 6 strategy) pass.

## Log

- Files touched: `src/agentic_dynamics/measurement/{efficiency,basin,recovery_cost,constraint_detection}.py`,
  `src/agentic_dynamics/reporting/game_report.py`, `scripts/sweep_silent_mode.py`,
  `tests/test_ratio_null_not_zero.py` (new).
- PASS: strategy.py verified already-None; 4 offenders None-guarded; consumers updated; ruff
  clean on the touched modules; guard tests green.
