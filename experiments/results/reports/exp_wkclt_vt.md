# Game Report: exp_wkclt_vt-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Building Flask task management API + flaw analysis...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:44:11

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.758

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.62) with moderate resource use ($0.0157, ~4138J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 8.5% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 98% (53/54 tests) [M] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 853 |
| Cyclomatic complexity [C] | 92.0 |
| Code quality [H] | 0.117 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.620** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,926 |
| Completion tokens [M] | 11,099 |
| Reasoning tokens [M] | 1,853 |
| Cache read tokens [M] | 157,696 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **21,878** |
| Thinking ratio [C] | 8.5% |
| Output efficiency [C] | 50.7% |
| Input cost [M] | $0.001025 |
| Output cost [M] | $0.005194 |
| Reasoning cost [M] | $0.000110 |
| Cache cost [M] | $0.009393 |
| **Total cost** | **$0.015723** |
| **Total energy [X]** | **~4138 J** |
| Solution density [C] | 0.038989 LOC/tok |
| Correctness/$ [C] | 27 |
| Quality/J [C] | 0.000150 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 98%  |  **Cost:** $0.0157  |  **Energy:** ~4138J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_wkclt_vt/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 853 |
| Functions | 77 |
| Classes | 13 |
| Functions/file | 7.7 |
| Classes/file | 1.3 |
| Avg lines/file | 85 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 26 |
| Decorators | 22 |
| Test files | 3 |
| Test file rate | 30% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 53 |
| Failed | 1 |
| Errors | 0 |
| Total | 54 |
| Pass rate | 98% |
| Duration | 25.5s |
