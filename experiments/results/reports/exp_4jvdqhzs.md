# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [remove_critical_constraint_s0.5_r1] gpt_gather_gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:14:44

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.838

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.6163, ~1443J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.736 |
| Architecture div [H] | 0.800 |
| Structure div [H] | 0.417 |
| Thinking ratio [C] | 3.8% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0007 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (14/14 tests) [M] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 305 |
| Cyclomatic complexity [C] | 50.0 |
| Code quality [H] | 0.328 |
| Novelty vs baseline [H] | 0.970 |
| **Composite [H]** | **0.861** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 33 |
| Completion tokens [M] | 5,792 |
| Reasoning tokens [M] | 230 |
| Cache read tokens [M] | 88,537 |
| Cache write tokens [M] | 13,287 |
| **Total tokens** | **6,055** |
| Thinking ratio [C] | 3.8% |
| Output efficiency [C] | 95.7% |
| Input cost [M] | $0.000171 |
| Output cost [M] | $0.239860 |
| Reasoning cost [M] | $0.009525 |
| Cache cost [M] | $0.366719 |
| **Total cost** | **$0.616274** |
| **Total energy [X]** | **~1443 J** |
| Solution density [C] | 0.050372 LOC/tok |
| Correctness/$ [C] | 7 |
| Quality/J [C] | 0.000597 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.6163  |  **Energy:** ~1443J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_4jvdqhzs/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 305 |
| Functions | 36 |
| Classes | 0 |
| Functions/file | 9.0 |
| Classes/file | 0.0 |
| Avg lines/file | 76 |
| Type hints | 31% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 17 |
| Decorators | 19 |
| Test files | 2 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 14 |
| Failed | 0 |
| Errors | 0 |
| Total | 14 |
| Pass rate | 100% |
| Duration | 3.0s |
