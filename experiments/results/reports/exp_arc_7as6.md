# Game Report: exp_arc_7as6-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Task management API with Flask, SQLite, JWT...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:17:44

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** WASTEFUL
**Score:** 0.195

**Verdict:** WASTEFUL — model burned 24,229 tokens ($0.0185, ~9031J, 75% thinking) achieving only 20% correctness. High reasoning overhead without convergence.

**Recommendation:** Reduce perturbation strength or avoid this operator class.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 74.8% |
| Quality/$ [C] | 54 |
| Quality/J [C] | 0.0001 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 20% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 4 |
| Cyclomatic complexity [C] | 2.0 |
| Code quality [H] | 0.967 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.338** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 5,943 |
| Completion tokens [M] | 161 |
| Reasoning tokens [M] | 18,125 |
| Cache read tokens [M] | 1,920 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **24,229** |
| Thinking ratio [C] | 74.8% |
| Output efficiency [C] | 0.7% |
| Input cost [M] | $0.006471 |
| Output cost [M] | $0.000714 |
| Reasoning cost [M] | $0.010232 |
| Cache cost [M] | $0.001084 |
| **Total cost** | **$0.018501** |
| **Total energy [X]** | **~9031 J** |
| Solution density [C] | 0.000165 LOC/tok |
| Correctness/$ [C] | 44 |
| Quality/J [C] | 0.000037 |

---

## Headline Metric
**Strategy:** WASTEFUL  |  **Correctness:** 20%  |  **Cost:** $0.0185  |  **Energy:** ~9031J  |  **Thinking:** 75%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_arc_7as6/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| Total lines (Py) | 4 |
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
