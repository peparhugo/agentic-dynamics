# Game Report: exp_6462vbw3-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API with JWT, pagination, rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:21:38

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.770

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0170, ~4012J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 2.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 748 |
| Cyclomatic complexity [C] | 72.0 |
| Code quality [H] | 0.134 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.709** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,058 |
| Completion tokens [M] | 11,954 |
| Reasoning tokens [M] | 634 |
| Cache read tokens [M] | 218,240 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **24,646** |
| Thinking ratio [C] | 2.6% |
| Output efficiency [C] | 48.5% |
| Input cost [M] | $0.001176 |
| Output cost [M] | $0.004748 |
| Reasoning cost [M] | $0.000032 |
| Cache cost [M] | $0.011032 |
| **Total cost** | **$0.016988** |
| **Total energy [X]** | **~4012 J** |
| Solution density [C] | 0.030350 LOC/tok |
| Correctness/$ [C] | 21 |
| Quality/J [C] | 0.000177 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0170  |  **Energy:** ~4012J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_6462vbw3/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 30 |
| Total lines (Py) | 748 |
| Functions | 94 |
| Classes | 11 |
| Functions/file | 3.1 |
| Classes/file | 0.4 |
| Avg lines/file | 25 |
| Type hints | 14% |
| Docstrings | 4% |
| Error handlers | 12 |
| Imports | 77 |
| Decorators | 51 |
| Test files | 5 |
| Test file rate | 17% |
| Parse errors | 0 |
