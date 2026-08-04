# Game Report: exp_er1n2rx3-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Task management API with Flask, SQLite, JWT, tests...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:52:08

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.62) with moderate resource use ($0.0191, ~4783J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.6% |
| Quality/$ | 55 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 945 |
| Cyclomatic complexity | 110.0 |
| Code quality | 0.106 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.618** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12,219 |
| Completion tokens | 13,446 |
| Reasoning tokens | 1,517 |
| **Total tokens** | **27,182** |
| Thinking ratio | 5.6% |
| Output efficiency | 49.5% |
| Input cost | $0.003299 |
| Output cost | $0.014791 |
| Reasoning cost | $0.000212 |
| **Total cost** | **$0.019105** |
| **Total energy** | **~4783 J** |
| Solution density | 0.034766 LOC/tok |
| Correctness/$ | 55 |
| Quality/J | 0.000129 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0191  |  **Energy:** ~4783J  |  **Thinking:** 6%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines | 945 |
| Functions | 88 |
| Classes | 10 |
| Functions/file | 12.6 |
| Classes/file | 1.4 |
| Avg lines/file | 135 |
| Type hints | 3% |
| Docstrings | 0% |
| Error handlers | 1 |
| Imports | 26 |
| Decorators | 19 |
| Test files | 1 |
| Test file rate | 14% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_er1n2rx3/code/)
