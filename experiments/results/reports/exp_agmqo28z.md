# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:15:50

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.749

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0142, ~3854J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 12.8% |
| Quality/$ [C] | 71 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 706 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.142 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.710** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,055 |
| Completion tokens [M] | 8,375 |
| Reasoning tokens [M] | 2,561 |
| Cache read tokens [M] | 198,272 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,991** |
| Thinking ratio [C] | 12.8% |
| Output efficiency [C] | 41.9% |
| Input cost [M] | $0.000871 |
| Output cost [M] | $0.003283 |
| Reasoning cost [M] | $0.000128 |
| Cache cost [M] | $0.009891 |
| **Total cost** | **$0.014172** |
| **Total energy [X]** | **~3854 J** |
| Solution density [C] | 0.035316 LOC/tok |
| Correctness/$ [C] | 25 |
| Quality/J [C] | 0.000184 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0142  |  **Energy:** ~3854J  |  **Thinking:** 13%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_agmqo28z/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 11 |
| Total lines (Py) | 706 |
| Functions | 63 |
| Classes | 13 |
| Functions/file | 5.7 |
| Classes/file | 1.2 |
| Avg lines/file | 64 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 43 |
| Decorators | 25 |
| Test files | 2 |
| Test file rate | 18% |
| Parse errors | 0 |
