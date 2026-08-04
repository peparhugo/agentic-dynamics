# Game Report: factorial_compound-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:factorial_compound:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:49:46

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.763

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.61) with moderate resource use ($0.0215, ~5645J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 6.0% |
| Quality/$ | 45 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 1537 |
| Cyclomatic complexity | 197.0 |
| Code quality | 0.065 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.609** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,196 |
| Completion tokens | 17,849 |
| Reasoning tokens | 1,711 |
| **Total tokens** | **28,756** |
| Thinking ratio | 6.0% |
| Output efficiency | 62.1% |
| Input cost | $0.002483 |
| Output cost | $0.019634 |
| Reasoning cost | $0.000240 |
| **Total cost** | **$0.021470** |
| **Total energy** | **~5645 J** |
| Solution density | 0.053450 LOC/tok |
| Correctness/$ | 45 |
| Quality/J | 0.000108 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0215  |  **Energy:** ~5645J  |  **Thinking:** 6%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 5 |
| Total lines | 1537 |
| Functions | 141 |
| Classes | 16 |
| Functions/file | 28.2 |
| Classes/file | 3.2 |
| Avg lines/file | 307 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 20 |
| Decorators | 59 |
| Test files | 2 |
| Test file rate | 40% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_factorial_compound_natural/code/)
