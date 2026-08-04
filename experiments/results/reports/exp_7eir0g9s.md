# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [inject_phantom_success_s0.5_r2] cd_openai_GPT_5_mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:47:19

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.816

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0146, ~2132J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.400 |
| Architecture div | 0.250 |
| Structure div | 0.167 |
| Thinking ratio | 4.4% |
| Quality/$ | 135 |
| Quality/J | 0.0005 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 202 |
| Cyclomatic complexity | 42.0 |
| Code quality | 0.495 |
| Novelty vs baseline | 0.834 |
| **Composite** | **0.745** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 11,627 |
| Completion tokens | 3,786 |
| Reasoning tokens | 704 |
| **Total tokens** | **16,117** |
| Thinking ratio | 4.4% |
| Output efficiency | 23.5% |
| Input cost | $0.003139 |
| Output cost | $0.004165 |
| Reasoning cost | $0.000099 |
| **Total cost** | **$0.014559** |
| **Total energy** | **~2132 J** |
| Solution density | 0.012533 LOC/tok |
| Correctness/$ | 135 |
| Quality/J | 0.000350 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0146  |  **Energy:** ~2132J  |  **Thinking:** 4%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines | 202 |
| Functions | 22 |
| Classes | 0 |
| Functions/file | 2.4 |
| Classes/file | 0.0 |
| Avg lines/file | 22 |
| Type hints | 11% |
| Docstrings | 5% |
| Error handlers | 8 |
| Imports | 26 |
| Decorators | 12 |
| Test files | 2 |
| Test file rate | 22% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_7eir0g9s/code/)
