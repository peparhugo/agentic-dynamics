# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5.5  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_final_gpt_5_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:48:21

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.841

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.2251, ~1822J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.732 |
| Architecture div | 0.800 |
| Structure div | 0.403 |
| Thinking ratio | 2.5% |
| Quality/$ | 141 |
| Quality/J | 0.0005 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 247 |
| Cyclomatic complexity | 45.0 |
| Code quality | 0.405 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.834** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,383 |
| Completion tokens | 4,351 |
| Reasoning tokens | 320 |
| **Total tokens** | **13,054** |
| Thinking ratio | 2.5% |
| Output efficiency | 33.3% |
| Input cost | $0.002263 |
| Output cost | $0.004786 |
| Reasoning cost | $0.000045 |
| **Total cost** | **$0.225053** |
| **Total energy** | **~1822 J** |
| Solution density | 0.018921 LOC/tok |
| Correctness/$ | 141 |
| Quality/J | 0.000458 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.2251  |  **Energy:** ~1822J  |  **Thinking:** 2%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines | 247 |
| Functions | 30 |
| Classes | 1 |
| Functions/file | 7.5 |
| Classes/file | 0.2 |
| Avg lines/file | 62 |
| Type hints | 35% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 12 |
| Decorators | 18 |
| Test files | 2 |
| Test file rate | 50% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_a90ybf13/code/)
