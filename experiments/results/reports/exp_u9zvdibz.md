# Game Report: exp_u9zvdibz-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT, SQLite, and tests...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:41:45

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.760

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.66) with moderate resource use ($0.0213, ~5411J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 7.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (66/83 tests) [M] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 1127 |
| Cyclomatic complexity [C] | 125.0 |
| Code quality [H] | 0.089 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.657** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 11,962 |
| Completion tokens [M] | 14,859 |
| Reasoning tokens [M] | 2,205 |
| Cache read tokens [M] | 354,560 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **29,026** |
| Thinking ratio [C] | 7.6% |
| Output efficiency [C] | 51.2% |
| Input cost [M] | $0.000991 |
| Output cost [M] | $0.005016 |
| Reasoning cost [M] | $0.000095 |
| Cache cost [M] | $0.015233 |
| **Total cost** | **$0.021334** |
| **Total energy [X]** | **~5411 J** |
| Solution density [C] | 0.038827 LOC/tok |
| Correctness/$ [C] | 14 |
| Quality/J [C] | 0.000121 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0213  |  **Energy:** ~5411J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_u9zvdibz/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 1127 |
| Functions | 117 |
| Classes | 10 |
| Functions/file | 11.7 |
| Classes/file | 1.0 |
| Avg lines/file | 113 |
| Type hints | 7% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 32 |
| Decorators | 29 |
| Test files | 3 |
| Test file rate | 30% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 66 |
| Failed | 17 |
| Errors | 0 |
| Total | 83 |
| Pass rate | 80% |
| Duration | 13.9s |
