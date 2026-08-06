# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r2] constraint_detection_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:05

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.807

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.76) with moderate resource use ($0.0115, ~2750J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.371 |
| Architecture div | 0.200 |
| Structure div | 0.211 |
| Thinking ratio | 3.3% |
| Quality/$ | 87 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 504 |
| Cyclomatic complexity | 89.0 |
| Code quality | 0.198 |
| Novelty vs baseline | 0.759 |
| **Composite** | **0.761** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,943 |
| Completion tokens | 7,684 |
| Reasoning tokens | 569 |
| **Total tokens** | **17,196** |
| Thinking ratio | 3.3% |
| Output efficiency | 44.7% |
| **Total cost** | **$0.011504** |
| **Total energy** | **~2750 J** |
| Solution density | 0.029309 LOC/tok |
| Correctness/$ | 91 |
| Quality/J | 0.000277 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0115  |  **Energy:** ~2750J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_nvn1kdwj/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 504 |
| Functions | 43 |
| Classes | 21 |
| Functions/file | 3.3 |
| Classes/file | 1.6 |
| Avg lines/file | 39 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 45 |
| Decorators | 10 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
