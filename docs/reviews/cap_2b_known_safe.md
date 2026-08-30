---
status: accepted
---

# cap_2b — known-safe list (p5 adversarial: attempted non-falsifying attacks)

**Campaign:** `cap_2b` (`cap_2b@0.1`). This document records the **non-falsifying** attacks that
were attempted in the adversarial pass and why each is safe. A falsifying attack would have been a
FAILED finding in `docs/reviews/cap_2b_adversary.md`; none of these falsified the verdict.

| # | attempted attack | evidence | why safe |
|---|---|---|---|
| K1 | Re-derive a **different** assignment from the committed seed (hoping the table was post-hoc fit) | `random.seed("fa74bbe6f9d4a67a019799ebfa61ac9e")` + the §4 block scheme reproduces the exact 18-cell table committed in the pre-registration; the pre-registration predates every cell run (commit order) | The table is seed-derivable, committed before data, and identical to what was analyzed |
| K2 | Find a cell scored under an **arm different from its assignment** | All 18 scored `(stimulus, arm, repetition)` tuples equal the seed-derived assignment (symmetric difference empty) | No arm mislabel survived; join validation is explicit |
| K3 | Find a **dropped cell** (a table row with no result) | 18/18 table rows scored; `n_invalid_join=0`; 0 stopped cells | Denominators are complete |
| K4 | Find a **redefined margin** in the score/verdict | `score.decision_rule.margin_*` equal the pre-registration §2 values verbatim (1.10, 0.05); verdict cites §2/§5 | No post-hoc margin change |
| K5 | Find an **applied static-arm proposal** | All 9 static cells: `applied_or_null=not_applicable`, proposal artifacts `"applied": false`, no extra commit in any static trail | Static proposals provably never applied |
| K6 | Find an **unprovable adaptive rework** | Each of the 3 adaptive critical cells has a `[workflow] rework` commit (single-line `calc.py` boundary fix, no test changes) | Applications are provable in the commit trail |
| K7 | Find **weakened tests** in any rework | Every rework diff touches only `calc.py`; `test_calc.py` is untouched in all 3 rework commits | No test weakening |
| K8 | Find a **fabricated cost** | Recorded cell costs equal each run ledger's `total_cost_usd` (17/17 p2 cells); the E4 cost equals the p1 phase ledger | Costs are ledger-sourced |
| K9 | Find an **outcome not independently verified** | Independent `pytest` re-run on every final commit matches the recorded `test_executed_success` for all 18 cells; defect determination = post-hoc `test_classify` on the immutable commit | Outcomes are independent of the proposing agent |
| K10 | Find a **secret/credential** in committed artifacts | `git grep` for `sk-…`, api keys, passwords across `experiments/results/cap_2b/` + the cap_2b docs → no matches | No secrets committed |
| K11 | Find a **guard breach / stopped cell** | Total spend $0.1744 vs $30.00 stop budget; no cell over 2× forecast; `stopped_cells=[]` | Budget/SLA guard held |
| K12 | Find a **treatment change** during the campaign | `git log 19e47b60b..HEAD` on `verify_proposal.py` / `code_change_facts.py` → empty; cell + campaign specs unchanged | Treatment is code-unchanged |
| K13 | Find a **hash mismatch** that indicates tampering | Score JSON SHA256 equals the validation pin; 73/74 p2 artifact-index hashes match (the 1 stale entry is a documented snapshot-timing edit, L1) | Only the documented, benign index-staleness; no scored artifact is mis-hashed |
| K14 | Find **post-hoc margin renegotiation** in the verdict | The verdict's decision is computed from the pre-registered rule only; CI (ratio upper 0.9105) is reported, not used to loosen the margin | Descriptive framing; the margin is untouched |

**Attempted attacks that were non-falsifying:** none of K1–K14 falsified the pre-registered
decision or any of its inputs. The verdict (`docs/experiments/results/cap_2b.md`, NON-INFERIOR) stands
unchanged.

**LOG:** 14 attempted non-falsifying attacks, 14 safe. **PASS** — commit.
