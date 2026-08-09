# Game Report: exp_er1n2rx3-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Task management API with Flask, SQLite, JWT, tests...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:32:05

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.66) with moderate resource use ($0.0191, ~4783J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 5.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 97% (65/67 tests) [M] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 945 |
| Cyclomatic complexity [C] | 110.0 |
| Code quality [H] | 0.106 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.660** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,219 |
| Completion tokens [M] | 13,446 |
| Reasoning tokens [M] | 1,517 |
| Cache read tokens [M] | 212,992 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,182** |
| Thinking ratio [C] | 5.6% |
| Output efficiency [C] | 49.5% |
| Input cost [M] | $0.001310 |
| Output cost [M] | $0.005872 |
| Reasoning cost [M] | $0.000084 |
| Cache cost [M] | $0.011839 |
| **Total cost** | **$0.019105** |
| **Total energy [X]** | **~4783 J** |
| Solution density [C] | 0.034766 LOC/tok |
| Correctness/$ [C] | 21 |
| Quality/J [C] | 0.000138 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 97%  |  **Cost:** $0.0191  |  **Energy:** ~4783J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_er1n2rx3/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 945 |
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

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 65 |
| Failed | 2 |
| Errors | 0 |
| Total | 67 |
| Pass rate | 97% |
| Duration | 24.3s |
