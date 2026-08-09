# Game Report: exp_1erxln69-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT and SQLite...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:18:10

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.57) with moderate resource use ($0.0214, ~5245J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 4.1% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 76% (68/90 tests) [M] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 1266 |
| Cyclomatic complexity [C] | 180.0 |
| Code quality [H] | 0.079 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.569** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,187 |
| Completion tokens [M] | 17,302 |
| Reasoning tokens [M] | 1,129 |
| Cache read tokens [M] | 389,760 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,618** |
| Thinking ratio [C] | 4.1% |
| Output efficiency [C] | 62.6% |
| Input cost [M] | $0.000698 |
| Output cost [M] | $0.005353 |
| Reasoning cost [M] | $0.000044 |
| Cache cost [M] | $0.015349 |
| **Total cost** | **$0.021444** |
| **Total energy [X]** | **~5245 J** |
| Solution density [C] | 0.045840 LOC/tok |
| Correctness/$ [C] | 13 |
| Quality/J [C] | 0.000109 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 76%  |  **Cost:** $0.0214  |  **Energy:** ~5245J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_1erxln69/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 18 |
| Total lines (Py) | 1266 |
| Functions | 126 |
| Classes | 5 |
| Functions/file | 7.0 |
| Classes/file | 0.3 |
| Avg lines/file | 70 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 50 |
| Decorators | 38 |
| Test files | 5 |
| Test file rate | 28% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 68 |
| Failed | 22 |
| Errors | 0 |
| Total | 90 |
| Pass rate | 76% |
| Duration | 33.9s |
