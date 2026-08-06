# Game Report: baseline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:baseline:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:50:36

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.760

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0145, ~3546J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.3% |
| Quality/$ | 69 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 697 |
| Cyclomatic complexity | 69.0 |
| Code quality | 0.143 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.711** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,559 |
| Completion tokens | 9,529 |
| Reasoning tokens | 1,424 |
| **Total tokens** | **19,512** |
| Thinking ratio | 7.3% |
| Output efficiency | 48.8% |
| **Total cost** | **$0.014543** |
| **Total energy** | **~3546 J** |
| Solution density | 0.035722 LOC/tok |
| Correctness/$ | 77 |
| Quality/J | 0.000200 |

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
