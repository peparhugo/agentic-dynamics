# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_final_gpt_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:54:14

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.834

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0634, ~2031J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.729 |
| Architecture div | 0.800 |
| Structure div | 0.393 |
| Thinking ratio | 5.6% |
| Quality/$ | 147 |
| Quality/J | 0.0005 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 203 |
| Cyclomatic complexity | 43.0 |
| Code quality | 0.493 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.808** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,457 |
| Completion tokens | 3,494 |
| Reasoning tokens | 832 |
| **Total tokens** | **14,783** |
| Thinking ratio | 5.6% |
| Output efficiency | 23.6% |
| Input cost | $0.002823 |
| Output cost | $0.003843 |
| Reasoning cost | $0.000116 |
| **Total cost** | **$0.063435** |
| **Total energy** | **~2031 J** |
| Solution density | 0.013732 LOC/tok |
| Correctness/$ | 147 |
| Quality/J | 0.000398 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0634  |  **Energy:** ~2031J  |  **Thinking:** 6%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines | 203 |
| Functions | 27 |
| Classes | 1 |
| Functions/file | 4.5 |
| Classes/file | 0.2 |
| Avg lines/file | 34 |
| Type hints | 43% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 20 |
| Decorators | 9 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_lw9zhue9/code/)
