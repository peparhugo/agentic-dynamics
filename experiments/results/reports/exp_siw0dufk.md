# Game Report: std_final-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [std_final] gpt_5_mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:58

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.810

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.61) with moderate resource use ($0.0159, ~2796J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.417 |
| Architecture div | 0.250 |
| Structure div | 0.227 |
| Thinking ratio | 7.1% |
| Quality/$ | 117 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 221 |
| Cyclomatic complexity | 41.0 |
| Code quality | 0.452 |
| Novelty vs baseline | 0.831 |
| **Composite** | **0.608** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 15,572 |
| Completion tokens | 3,733 |
| Reasoning tokens | 1,472 |
| **Total tokens** | **20,777** |
| Thinking ratio | 7.1% |
| Output efficiency | 18.0% |
| Input cost | $0.004204 |
| Output cost | $0.004106 |
| Reasoning cost | $0.000206 |
| **Total cost** | **$0.015874** |
| **Total energy** | **~2796 J** |
| Solution density | 0.010637 LOC/tok |
| Correctness/$ | 117 |
| Quality/J | 0.000217 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0159  |  **Energy:** ~2796J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines | 221 |
| Functions | 18 |
| Classes | 0 |
| Functions/file | 6.0 |
| Classes/file | 0.0 |
| Avg lines/file | 74 |
| Type hints | 19% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 15 |
| Decorators | 6 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_siw0dufk/code/)
