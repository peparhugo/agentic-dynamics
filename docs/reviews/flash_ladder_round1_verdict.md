---
status: accepted
---

# flash-exploration ladder — round 1 verdict

**Question.** Does `deepseek/deepseek-v4-flash`'s design behaviour move under divergence
framing, a larger thinking budget, or retrieval augmentation with the knowledge base — measured
as portfolio diversity across independent attempts, paired with independently tested quality?

**Design (pre-registered before any cell).** 4 conditions × 3 independent reps, base
`121126dfbcd65a656883e3f3cc81b12e612aeeeb`; the task is the `taskman` contract
(`tests/flash_ladder/taskman_contract_test.py`), generated in one session per cell. Conditions:
C0 neutral; C1 divergence framing; C2 high thinking (`--thinking-budget-tokens 32000`); C3
KB-augmented (`rag_augment`, shared scope `agentic-dynamics`/`public`, `pattern_projection`).
Harness, specs, and safety rails pinned in pre-registration addendum §12; the evidence is
frozen at `experiments/ladder_evidence/round1/`.

## Results (score `ladder-cells/v1`, verified)

| Cond | valid | Q (pristine 13/13) | D (mean composite) | ΔD vs C0 | 95% CI (descriptive) | distinct_frac | median cost |
|---|---|---|---|---|---|---|---|
| C0 neutral | 3/3 | 3/3 | 0.3571 | — | [0.000, 0.357] | 0.000 | $0.0104 |
| C1 framing | 3/3 | 3/3 | 0.3626 | +0.0055 | [0.000, 0.363] | 0.000 | $0.0198 |
| C2 thinking | 3/3 | 3/3 | 0.4072 | +0.0501 | [0.000, 0.407] | 0.000 | $0.0093 |
| C3 KB | 3/3 | 3/3 | 0.4194 | +0.0623 | [0.000, 0.419] | 0.000 | $0.0100 |

**Decision (pre-registered rule): FLAT.** No condition reaches |ΔD| ≥ 0.10 or |ΔQ| ≥ 1; the
registered directive is "flat within the registered margin; no policy claim". No confirmatory
grid is triggered.

## Verification

- **Independent score review: PASS** (`docs/reviews/flash_ladder_score_review.md`, terra,
  `run-7fc52c6e45c0`): the reviewer replayed `scripts/score_flash_ladder.py` from the committed
  exports, reproduced every Q, D, exclusion, bootstrap, delta, and decision value, and ran the
  scorer + diversity suites (20/20).
- **Limitations recorded by the review:** cell commit SHAs recorded in the cell records do not
  resolve inside the review clone (the run clones are the source of truth), and ledger payloads
  were not part of the frozen evidence, so cost/token and C3 augmentation fields could not be
  independently replayed. Neither enters Q, D, or the decision.
- **C3 condition state (from the cell ledgers, host-side):** all three cells ran
  `fallback_mode="lexical_graph_only"` with the deterministic constructor and selected 3
  evidence records each — the KB arm retrieved; the dense leg is host-side by network design.
  The evidence set is identical across the three reps (same base commit, same query), so the C3
  treatment is constant rather than varied.

## Interpretation and limits

- **Quality saturated**: all twelve cells passed 13/13 pristine, so the task cannot
  discriminate quality between conditions at this difficulty.
- **Diversity effects are small and uncertain**: C2 and C3 show the largest positive deltas
  (+0.05, +0.06) but are well inside the registered 0.10 margin; n=3 CIs span from 0 (a known
  bootstrap artifact at this n) to the point estimate, and are descriptive only.
- **No pair cleared the 0.5 distinctness threshold** in any condition (`distinct_fraction 0`):
  flash's designs are variations on one theme, not distinct architectures.
- **Task caveat**: the contract is deliberately small; diversity conclusions are about this
  task family, not about design creativity in general.

## Next turns

1. **Scope 1 (queued):** distill the passing designs into the first self-derived skill record,
   ingest it, and run a **C4 skill-augmented arm** (3 reps, separately pre-registered) against
   C0 — the loop's first "explore → derive skill → reuse → measure" turn.
2. **Scope 2:** build the research & synthesis layer
   (`docs/designs/proposed/research_synthesis_layer.md`) and apply it to the Control Room
   facelift, with SVG handling as the measured pilot.
