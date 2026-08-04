# Game Report: remove_critical_constraint_s0.5_r2-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [remove_critical_constraint_s0.5_r2] cd_claude_2rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T03:09:34

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.814

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($1.2247, ~3149J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.383 |
| Architecture div | 0.200 |
| Structure div | 0.250 |
| Thinking ratio | 0.0% |
| Quality/$ | 66 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 634 |
| Cyclomatic complexity | 116.0 |
| Code quality | 0.158 |
| Novelty vs baseline | 0.759 |
| **Composite** | **0.753** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 28 |
| Completion tokens | 13,683 |
| Reasoning tokens | 0 |
| **Total tokens** | **13,711** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000008 |
| Output cost | $0.015051 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$1.224702** |
| **Total energy** | **~3149 J** |
| Solution density | 0.046240 LOC/tok |
| Correctness/$ | 66 |
| Quality/J | 0.000239 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $1.2247  |  **Energy:** ~3149J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 14 |
| Total lines | 634 |
| Functions | 56 |
| Classes | 18 |
| Functions/file | 4.0 |
| Classes/file | 1.3 |
| Avg lines/file | 45 |
| Type hints | 46% |
| Docstrings | 18% |
| Error handlers | 6 |
| Imports | 45 |
| Decorators | 34 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_yl5gcl6d/code/)
