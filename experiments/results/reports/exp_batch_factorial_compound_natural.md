# Game Report: factorial_compound-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:factorial_compound:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:27:51

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.763

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.57) with moderate resource use ($0.0215, ~5645J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 6.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 92% (81/88 tests) [M] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 1537 |
| Cyclomatic complexity [C] | 197.0 |
| Code quality [H] | 0.065 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.567** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,196 |
| Completion tokens [M] | 17,849 |
| Reasoning tokens [M] | 1,711 |
| Cache read tokens [M] | 124,800 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **28,756** |
| Thinking ratio [C] | 6.0% |
| Output efficiency [C] | 62.1% |
| Input cost [M] | $0.001338 |
| Output cost [M] | $0.010584 |
| Reasoning cost [M] | $0.000129 |
| Cache cost [M] | $0.009418 |
| **Total cost** | **$0.021470** |
| **Total energy [X]** | **~5645 J** |
| Solution density [C] | 0.053450 LOC/tok |
| Correctness/$ [C] | 25 |
| Quality/J [C] | 0.000100 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 92%  |  **Cost:** $0.0215  |  **Energy:** ~5645J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_factorial_compound_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 5 |
| Total lines (Py) | 1537 |
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

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 81 |
| Failed | 7 |
| Errors | 0 |
| Total | 88 |
| Pass rate | 92% |
| Duration | 43.6s |
