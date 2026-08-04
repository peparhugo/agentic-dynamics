# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:48:21

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.749

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.62) with moderate resource use ($0.0142, ~3854J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 12.8% |
| Quality/$ | 83 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 706 |
| Cyclomatic complexity | 89.0 |
| Code quality | 0.142 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.625** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,055 |
| Completion tokens | 8,375 |
| Reasoning tokens | 2,561 |
| **Total tokens** | **19,991** |
| Thinking ratio | 12.8% |
| Output efficiency | 41.9% |
| Input cost | $0.002445 |
| Output cost | $0.009213 |
| Reasoning cost | $0.000359 |
| **Total cost** | **$0.014172** |
| **Total energy** | **~3854 J** |
| Solution density | 0.035316 LOC/tok |
| Correctness/$ | 83 |
| Quality/J | 0.000162 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0142  |  **Energy:** ~3854J  |  **Thinking:** 13%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 11 |
| Total lines | 706 |
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

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_agmqo28z/code/)
