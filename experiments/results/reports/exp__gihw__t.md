# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** openai/gpt-5.5  |  **Task:** [remove_critical_constraint_s0.5_r1] gpt_gather_gpt_5_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:48:21

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.826

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.81) with moderate resource use ($0.3050, ~2980J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.468 |
| Architecture div | 0.500 |
| Structure div | 0.042 |
| Thinking ratio | 0.8% |
| Quality/$ | 89 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 251 |
| Cyclomatic complexity | 41.0 |
| Code quality | 0.398 |
| Novelty vs baseline | 0.852 |
| **Composite** | **0.815** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 22,181 |
| Completion tokens | 4,771 |
| Reasoning tokens | 230 |
| **Total tokens** | **27,182** |
| Thinking ratio | 0.8% |
| Output efficiency | 17.6% |
| Input cost | $0.005989 |
| Output cost | $0.005248 |
| Reasoning cost | $0.000032 |
| **Total cost** | **$0.304967** |
| **Total energy** | **~2980 J** |
| Solution density | 0.009234 LOC/tok |
| Correctness/$ | 89 |
| Quality/J | 0.000273 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3050  |  **Energy:** ~2980J  |  **Thinking:** 1%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 251 |
| Functions | 34 |
| Classes | 2 |
| Functions/file | 17.0 |
| Classes/file | 1.0 |
| Avg lines/file | 126 |
| Type hints | 43% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 13 |
| Decorators | 13 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp__gihw__t/code/)
