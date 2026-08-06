# Game Report: baseline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:baseline:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:28:08

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.760

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0145, ~3546J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.3% |
| Quality/$ [C] | 69 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 697 |
| Cyclomatic complexity [C] | 69.0 |
| Code quality [H] | 0.143 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.711** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,559 |
| Completion tokens [M] | 9,529 |
| Reasoning tokens [M] | 1,424 |
| Cache read tokens [M] | 355,968 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,512** |
| Thinking ratio [C] | 7.3% |
| Output efficiency [C] | 48.8% |
| Input cost [M] | $0.000535 |
| Output cost [M] | $0.002426 |
| Reasoning cost [M] | $0.000046 |
| Cache cost [M] | $0.011535 |
| **Total cost** | **$0.014543** |
| **Total energy [X]** | **~3546 J** |
| Solution density [C] | 0.035722 LOC/tok |
| Correctness/$ [C] | 16 |
| Quality/J [C] | 0.000200 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0145  |  **Energy:** ~3546J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_mho8njwt/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 24 |
| Total lines (Py) | 697 |
| Functions | 55 |
| Classes | 19 |
| Functions/file | 2.3 |
| Classes/file | 0.8 |
| Avg lines/file | 29 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 17 |
| Imports | 78 |
| Decorators | 40 |
| Test files | 2 |
| Test file rate | 8% |
| Parse errors | 0 |
