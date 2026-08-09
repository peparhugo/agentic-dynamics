# Game Report: baseline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:baseline:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:46:11

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.761

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.0165, ~4053J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 6.8% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 885 |
| Cyclomatic complexity [C] | 74.0 |
| Code quality [H] | 0.113 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.705** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,204 |
| Completion tokens [M] | 11,347 |
| Reasoning tokens [M] | 1,505 |
| Cache read tokens [M] | 361,856 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,056** |
| Thinking ratio [C] | 6.8% |
| Output efficiency [C] | 51.4% |
| Input cost [M] | $0.000623 |
| Output cost [M] | $0.003128 |
| Reasoning cost [M] | $0.000053 |
| Cache cost [M] | $0.012694 |
| **Total cost** | **$0.016497** |
| **Total energy [X]** | **~4053 J** |
| Solution density [C] | 0.040125 LOC/tok |
| Correctness/$ [C] | 15 |
| Quality/J [C] | 0.000174 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0165  |  **Energy:** ~4053J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_zg0opvwm/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 18 |
| Total lines (Py) | 885 |
| Functions | 91 |
| Classes | 8 |
| Functions/file | 5.1 |
| Classes/file | 0.4 |
| Avg lines/file | 49 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 46 |
| Decorators | 32 |
| Test files | 6 |
| Test file rate | 33% |
| Parse errors | 0 |
