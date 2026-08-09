# Game Report: std_final-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [std_final] gpt-5.6-fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:21:42

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.825

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.96, correctness=100%). Cost: $0.6268, ~1498J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.746 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.385 |
| Thinking ratio [C] | 9.5% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0007 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (8/8 tests) [M] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 292 |
| Cyclomatic complexity [C] | 32.0 |
| Code quality [H] | 0.342 |
| Novelty vs baseline [H] | 0.960 |
| **Composite [H]** | **0.691** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 36 |
| Completion tokens [M] | 5,349 |
| Reasoning tokens [M] | 564 |
| Cache read tokens [M] | 105,977 |
| Cache write tokens [M] | 13,255 |
| **Total tokens** | **5,949** |
| Thinking ratio [C] | 9.5% |
| Output efficiency [C] | 89.9% |
| Input cost [M] | $0.000178 |
| Output cost [M] | $0.211467 |
| Reasoning cost [M] | $0.022297 |
| Cache cost [M] | $0.392862 |
| **Total cost** | **$0.626804** |
| **Total energy [X]** | **~1498 J** |
| Solution density [C] | 0.049084 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000461 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.6268  |  **Energy:** ~1498J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_6w9zsvwr/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 5 |
| Total lines (Py) | 292 |
| Functions | 26 |
| Classes | 0 |
| Functions/file | 5.2 |
| Classes/file | 0.0 |
| Avg lines/file | 58 |
| Type hints | 38% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 15 |
| Decorators | 8 |
| Test files | 2 |
| Test file rate | 40% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 8 |
| Failed | 0 |
| Errors | 0 |
| Total | 8 |
| Pass rate | 100% |
| Duration | 1.3s |
