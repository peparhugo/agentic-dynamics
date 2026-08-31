# persistent_code_graph — p2 wall reproduction (the 2e wall, reproduced ON the persistent graph)

**Phase:** `p2_wall_reproduction` (spec `persistent_code_graph@0.1`).
**Role:** reproduce the 2e wall ON the persistent graph — BOUNDED to the query. The fixture:
the `incorrect_rebuilt` cells' changed symbols (the `widgets→add` dependants). The wall's two
facts, side-by-side in one artifact, plus the counter's behavioral definition — the semantics'
inspectability. Machine-readable twin:
`experiments/results/graph_family/wall_reproduction.json`. Query tool:
`scripts/graph_family_wall.py`.
**Date:** 2026-08-31.
**Graph service:** `bolt://localhost:7687` (the persistent code graph, built in p1).

## The wall's recorded facts (the artifacts, unchanged)

From `cap_adaptive_2d/p1_incorrect_rebuilt_probe.json` + the `cap2d_incorrect_rebuilt_*` cell
records:

| wall fact | recorded value | source |
|---|---|---|
| `impacted_symbol_count` | **0** | the probe + every `incorrect_rebuilt` cell's `facts.impacted_symbol_count` |
| `changed_symbol_count` | 20 | the probe + cell records (the 19 widgets added + `add` changed) |
| `changed_symbols_with_tests_ratio` | 0.05 | cell records (only `test_add`/`test_subtract` cover a changed symbol) |
| probe, 10s deadline | impacted **3**: `subtract, test_add, test_subtract` | the probe's `probe_verified_with_10s_deadline` |

## Fact 1 — the structural edges EXIST (live query, no deadline)

The persistent graph holds the `widgets→add` dependant edges for every `incorrect_rebuilt` cell.
For `self-cap2d_incorrect_rebuilt_status_quo_r1`, `add` has **20 inbound `CALLS` dependants**
(`test_add` + `widget_1..widget_19`); all four cells + the probe worktree show the same 20.

```
add ← CALLS ← widget_1      add ← CALLS ← widget_10     …   add ← CALLS ← widget_19
add ← CALLS ← test_add      (and, 2 hops out) test_subtract ← … ← subtract  (the probe's 10s set)
```

Per-cell live counts: `abstention_r1/r2` and `status_quo_r1/r2` each show **20** dependants on
`add` — the wall's structural edges, queryable, no truncation.

## Fact 2 — the impacted counter read 0 (the recorded value + the live trace)

**The counter's definition (behavioral — the 2e lesson, now inspectable):**

> the impact counter computes a **BEHAVIORAL** impact — a behavior-preserving change has zero
> behavioral impact on its callers — while the construction assumed **STRUCTURAL** reach (the
> callers' edges). Mechanically: the changed symbols are the **seeds**; the seeds themselves are
> excluded from the impacted set (`evidence_analyzer.py:235-247`), and the 20-seed BFS runs under
> a hard `timeout_ms=300` (`evidence_analyzer.py:225-234`), truncating before the non-seed
> dependants.

**The live trace against the persistent graph** — the analyzer's exact expansion
(`expand_candidates`, `max_depth=2, max_neighbors=8, max_nodes=40, IMPACT_EXPANSION_RELS`, 20
seeds), re-run at both deadlines:

| deadline | expansion nodes | impacted count | non-seed dependants |
|---|---|---|---|
| **300ms** (the recorded deadline) | 20 (the seeds only) | **0** | — |
| **10s** (the probe's verification) | 26 | **3** | `subtract, test_add, test_subtract` |

The 300ms trace reproduces the wall's **0** live; the 10s trace reproduces the probe's **3** with
the identical dependant set. The wall's `0` is the deadline truncation + seeds-exclusion, not a
missing edge — **both facts are now visible in one artifact.**

## Findings

1. **The wall is reproduced as a graph query.** The structural `widgets→add` dependant edges
   EXIST (20 per cell) AND the impacted counter read 0 (recorded) — the exact wall the 2d/2e
   campaigns hit — now checkable side-by-side against the persistent graph instead of a
   discarded per-change AST.
2. **The semantics are inspectable.** The behavioral-vs-structural divergence (the 2e lesson) is
   no longer a buried root-cause: the edges exist (structural), the counter is behavioral (the
   seeds-exclusion + deadline), and the live trace shows the 0↔3 flip at the 300ms↔10s deadline.
3. **The divergence mechanism is confirmed, not inferred.** The probe's root-cause (deadline
   truncation; only `subtract/test_add/test_subtract` are the non-seed dependants) is reproduced
   exactly by re-running the analyzer against the persistent graph.

## Honest limits

- The `0` is the *recorded* wall fact; the 300ms trace reproduces it live on a warm graph today,
  but a faster machine could complete the 20-seed expansion inside 300ms and read 3 — that is
  precisely the nondeterminism the wall exposed (the deadline is the bug, not the graph).
- The reproduction covers the four `incorrect_rebuilt` cells + the probe worktree; the other
  2d/2e families are out of scope for this bounded phase.

**LOG:** the structural edges found live (20 `widgets→add` dependants per `incorrect_rebuilt`
cell); the impacted counter's recorded 0 + the behavioral definition reproduced side-by-side; the
live analyzer trace flips 0 (300ms) → 3 (10s) with the probe's exact dependant set. **PASS.**
