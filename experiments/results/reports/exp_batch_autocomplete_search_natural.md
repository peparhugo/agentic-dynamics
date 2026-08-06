# Game Report: autocomplete_search-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:autocomplete_search:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:18:29

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.743

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.57) with moderate resource use ($0.0180, ~5350J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 16.1% |
| Quality/$ [C] | 56 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 98% (66/67 tests) [M] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 1186 |
| Cyclomatic complexity [C] | 191.0 |
| Code quality [H] | 0.084 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.570** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6,438 |
| Completion tokens [M] | 13,278 |
| Reasoning tokens [M] | 3,790 |
| Cache read tokens [M] | 96,256 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,506** |
| Thinking ratio [C] | 16.1% |
| Output efficiency [C] | 56.5% |
| Input cost [M] | $0.001031 |
| Output cost [M] | $0.008662 |
| Reasoning cost [M] | $0.000315 |
| Cache cost [M] | $0.007992 |
| **Total cost** | **$0.017999** |
| **Total energy [X]** | **~5350 J** |
| Solution density [C] | 0.050455 LOC/tok |
| Correctness/$ [C] | 33 |
| Quality/J [C] | 0.000107 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 98%  |  **Cost:** $0.0180  |  **Energy:** ~5350J  |  **Thinking:** 16%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_autocomplete_search_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 12 |
| Total lines (Py) | 1186 |
| Functions | 92 |
| Classes | 10 |
| Functions/file | 7.7 |
| Classes/file | 0.8 |
| Avg lines/file | 99 |
| Type hints | 6% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 27 |
| Decorators | 9 |
| Test files | 5 |
| Test file rate | 42% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 66 |
| Failed | 1 |
| Errors | 0 |
| Total | 67 |
| Pass rate | 98% |
| Duration | 0.9s |
