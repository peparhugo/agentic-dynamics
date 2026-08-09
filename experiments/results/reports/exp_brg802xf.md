# Game Report: invert_constraint_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:29:54

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.765

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.68) and found a novel correct solution (novelty=0.98, correctness=80%). Cost: $0.1849, ~5284J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.675 |
| Architecture div [H] | 0.600 |
| Structure div [H] | 0.467 |
| Thinking ratio [C] | 6.1% |
| Quality/$ [C] | 5 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (3/3 tests) [M] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 476 |
| Cyclomatic complexity [C] | 76.0 |
| Code quality [H] | 0.210 |
| Novelty vs baseline [H] | 0.984 |
| **Composite [H]** | **0.512** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 26,522 |
| Completion tokens [M] | 9,040 |
| Reasoning tokens [M] | 2,304 |
| Cache read tokens [M] | 306,816 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **37,866** |
| Thinking ratio [C] | 6.1% |
| Output efficiency [C] | 23.9% |
| Input cost [M] | $0.018121 |
| Output cost [M] | $0.049413 |
| Reasoning cost [M] | $0.012594 |
| Cache cost [M] | $0.104817 |
| **Total cost** | **$0.184944** |
| **Total energy [X]** | **~5284 J** |
| Solution density [C] | 0.012571 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000097 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.1849  |  **Energy:** ~5284J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_brg802xf/session.jsonl)
- [Generated code](./exp_brg802xf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 443 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 3 |
| Failed | 0 |
| Errors | 0 |
| Total | 3 |
| Pass rate | 100% |
| Duration | 3.5s |
