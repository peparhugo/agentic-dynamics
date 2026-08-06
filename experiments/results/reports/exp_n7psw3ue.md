# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:02

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.711

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0206, ~7178J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 31.9% |
| Quality/$ | 49 |
| Quality/J | 0.0001 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 694 |
| Cyclomatic complexity | 53.0 |
| Code quality | 0.144 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.711** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 15,343 |
| Completion tokens | 5,702 |
| Reasoning tokens | 9,871 |
| **Total tokens** | **30,916** |
| Thinking ratio | 31.9% |
| Output efficiency | 18.4% |
| **Total cost** | **$0.020584** |
| **Total energy** | **~7178 J** |
| Solution density | 0.022448 LOC/tok |
| Correctness/$ | 85 |
| Quality/J | 0.000099 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0206  |  **Energy:** ~7178J  |  **Thinking:** 32%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_n7psw3ue/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 16 |
| Total lines (Py) | 694 |
| Functions | 57 |
| Classes | 18 |
| Functions/file | 3.6 |
| Classes/file | 1.1 |
| Avg lines/file | 43 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 11 |
| Imports | 48 |
| Decorators | 24 |
| Test files | 2 |
| Test file rate | 12% |
| Parse errors | 0 |
