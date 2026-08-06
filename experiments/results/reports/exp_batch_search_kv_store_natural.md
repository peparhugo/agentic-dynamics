# Game Report: search_kv_store-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:search_kv_store:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:21:37

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.48) with moderate resource use ($0.0177, ~4658J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.8% |
| Quality/$ [C] | 56 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 1239 |
| Cyclomatic complexity [C] | 357.0 |
| Code quality [H] | 0.081 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.484** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,557 |
| Completion tokens [M] | 13,892 |
| Reasoning tokens [M] | 1,826 |
| Cache read tokens [M] | 207,360 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,275** |
| Thinking ratio [C] | 7.8% |
| Output efficiency [C] | 59.7% |
| Input cost [M] | $0.000775 |
| Output cost [M] | $0.005808 |
| Reasoning cost [M] | $0.000097 |
| Cache cost [M] | $0.011033 |
| **Total cost** | **$0.017714** |
| **Total energy [X]** | **~4658 J** |
| Solution density [C] | 0.053233 LOC/tok |
| Correctness/$ [C] | 21 |
| Quality/J [C] | 0.000104 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0177  |  **Energy:** ~4658J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_search_kv_store_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 1239 |
| Functions | 60 |
| Classes | 7 |
| Functions/file | 7.5 |
| Classes/file | 0.9 |
| Avg lines/file | 155 |
| Type hints | 3% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 13 |
| Decorators | 0 |
| Test files | 1 |
| Test file rate | 12% |
| Parse errors | 5 |
