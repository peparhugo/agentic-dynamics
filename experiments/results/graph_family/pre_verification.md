# persistent_code_graph — p3 pre-verification (the campaign-time query, asked against the persistent graph)

**Phase:** `p3_pre_verification` (spec `persistent_code_graph@0.1`).
**Role:** the campaign-time pre-verification — BOUNDED to the query. The pinned question (spec
hard rule 5): **"does this construction's changed symbol have structural dependants?"** — asked
against the persistent graph for the 2d/2e cells' changed symbols AND a control symbol (a leaf
with no dependants). The answer visible + recorded (the dependant sets, per symbol).
Machine-readable twin: `experiments/results/graph_family/pre_verification.json`. Query tool:
`scripts/graph_family_preverify.py`.
**Date:** 2026-08-31.
**Graph service:** `bolt://localhost:7687` (the persistent code graph, built in p1).

## The pinned question

> **does this construction's changed symbol have structural dependants?** — asked BEFORE any grid,
> with the answer visible + recorded. The dependants are the inbound `CALLS` edges on the changed
> symbols' versions (the same structural edges the 2d/2e wall was about).

## The constructions queried (15 cells)

Per-cell: the construction's changed symbols (typed `CodeDelta`, seed→final) → per-symbol
structural dependants from the persistent graph.

| cell | class | changed | hub symbol | has structural dependants |
|---|---|---|---|---|
| `cap2d_incorrect_rebuilt_abstention_r1` | incorrect_rebuilt | 20 | `add` | **YES (20)** |
| `cap2d_incorrect_rebuilt_abstention_r2` | incorrect_rebuilt | 20 | `add` | **YES (20)** |
| `cap2d_incorrect_rebuilt_status_quo_r1` | incorrect_rebuilt | 20 | `add` | **YES (20)** |
| `cap2d_incorrect_rebuilt_status_quo_r2` | incorrect_rebuilt | 20 | `add` | **YES (20)** |
| `cap2d_correct_abstention_r1` | correct | 2 | `classify` | no |
| `cap2d_competing_abstention_r1` | competing | 2 | `classify` | no |
| `cap2d_harmful_partial_abstention_r1` | harmful_partial | 2 | `classify` | no |
| `cap2d_irrelevant_abstention_r1` | irrelevant | 2 | `product` | yes (1, `test_product`) |
| `cap2d_absent-clean_abstention_r1` | absent | 1 | `widget` | no |
| `cap2d_absent-defective_abstention_r1` | absent | 1 | `wrong_op` | no |
| `cap2d_unseen_family_abstention_r1` | unseen_family | 2 | `tally` | weak (1, `test_tally`) |
| `cap2e_absent-defective_abstention_r1` | absent | 1 | `wrong_op` | no |
| `cap2e_absent-defective_status_quo_r1` | absent | 1 | `wrong_op` | no |
| `cap2e_unseen_family_abstention_r1` | unseen_family | 2 | `tally` | weak (1, `test_tally`) |
| `cap2e_unseen_family_status_quo_r1` | unseen_family | 2 | `tally` | weak (1, `test_tally`) |

## The dependant sets (per symbol — the visible answer)

The wall's construction, live from the graph — `add` in every `incorrect_rebuilt` cell carries
**20 structural dependants** (`test_add` + `widget_1..widget_19`):

```
add  ←  CALLS  ←  widget_1, widget_10, …, widget_19, test_add      (20 dependants)
```

The changed symbols that changed nothing structurally (empty dependant sets): `classify`
(correct/competing/harmful_partial), `widget`/`wrong_op` (absent-defective), `product`
(irrelevant — 1 test-only dependant), `tally` (unseen_family — 1 test-only dependant).

## The controls (the query's negative + mid cases)

| control | symbol | dependant set | meaning |
|---|---|---|---|
| **leaf** | `widget_1` | **0 dependants** | the negative case — the query returns a clean NO |
| reference | `subtract` | 1 (`test_subtract`) | the mid case — a test-only dependant |

## The campaign-time answer

- **Caught BEFORE the grid (the wall):** the `incorrect_rebuilt` construction changes `add`,
  which has **20 structural dependants** → the pre-verification returns **VERIFY**. The 2d/2e
  wall (the construction assumed structural reach while the impacted counter measured behavioral
  impact) is exactly what this query would have surfaced at campaign time.
- **Weak signal:** the `unseen_family` construction changes `tally` (1 test-only dependant) —
  the structural signal is weak and its defect (input mutation) is behavioral, invisible to the
  structural question. The pre-verification is a structural tripwire, not a semantic oracle.
- **Negative case:** the leaf control `widget_1` has zero dependants — the query returns NO
  cleanly (a construction touching only leaves carries no structural blast radius).

## Findings

1. **The pre-verification is a query with a visible answer.** Every construction's changed
   symbol's dependant set is recorded per symbol; the wall's `add`→20 is the headline YES.
2. **The query discriminates.** The wall construction (20 dependants) vs the leaf control (0)
   vs the mid reference (1) — the three regimes the campaign would want to distinguish.
3. **The wall would have been caught pre-run.** The construction that hit the wall (change
   `add` in a codebase where the widgets call it) returns VERIFY — before any grid — which is
   the 2e lesson operationalized as a graph query.

## Honest limits

- The dependants are the structural `CALLS` set at the final revision; the query does not claim
  semantic reach (a behavioral defect invisible to the structure, e.g. the `tally` mutation,
  is out of the structural question's scope — stated as such in the verdict).
- Coverage is the wall cells + a representative spread across the 2d/2e families (15 cells); the
  full 28-cell 2d grid is out of scope for this bounded phase.

**LOG:** 15 cells queried (per-symbol dependant sets recorded); wall construction caught
(`add` → 20 dependants → VERIFY), unseen_family weak signal (`tally` → 1), leaf control negative
(`widget_1` → 0). **PASS.**
