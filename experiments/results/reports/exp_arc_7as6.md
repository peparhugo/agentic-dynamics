# Game Report: exp_arc_7as6-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Task management API with Flask, SQLite, JWT...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:48:21

---

## Strategy
**Classification:** WASTEFUL
**Score:** 0.195

**Verdict:** WASTEFUL — model burned 24,229 tokens ($0.0185, ~9031J, 75% thinking) achieving only 20% correctness. High reasoning overhead without convergence.

**Recommendation:** Reduce perturbation strength or avoid this operator class.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 74.8% |
| Quality/$ | 232 |
| Quality/J | 0.0001 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 20% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 4 |
| Cyclomatic complexity | 2.0 |
| Code quality | 0.967 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.338** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 5,943 |
| Completion tokens | 161 |
| Reasoning tokens | 18,125 |
| **Total tokens** | **24,229** |
| Thinking ratio | 74.8% |
| Output efficiency | 0.7% |
| Input cost | $0.001605 |
| Output cost | $0.000177 |
| Reasoning cost | $0.002538 |
| **Total cost** | **$0.018501** |
| **Total energy** | **~9031 J** |
| Solution density | 0.000165 LOC/tok |
| Correctness/$ | 46 |
| Quality/J | 0.000037 |

---

## Headline Metric
**Strategy:** WASTEFUL  |  **Correctness:** 20%  |  **Cost:** $0.0185  |  **Energy:** ~9031J  |  **Thinking:** 75%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| Total lines | 4 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0.0 |
| Classes/file | 0.0 |
| Avg lines/file | 4 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 1 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
