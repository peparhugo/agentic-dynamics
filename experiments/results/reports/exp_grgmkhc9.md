# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:33:27

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.828

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0250, ~6182J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.751 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.392 |
| Thinking ratio [C] | 8.9% |
| Quality/$ [C] | 40 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (7/7 tests) [M] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 1133 |
| Cyclomatic complexity [C] | 127.0 |
| Code quality [H] | 0.088 |
| Novelty vs baseline [H] | 0.970 |
| **Composite [H]** | **0.599** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 15,688 |
| Completion tokens [M] | 15,224 |
| Reasoning tokens [M] | 3,033 |
| Cache read tokens [M] | 640,512 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **33,945** |
| Thinking ratio [C] | 8.9% |
| Output efficiency [C] | 44.8% |
| Input cost [M] | $0.000954 |
| Output cost [M] | $0.003774 |
| Reasoning cost [M] | $0.000096 |
| Cache cost [M] | $0.020206 |
| **Total cost** | **$0.025030** |
| **Total energy [X]** | **~6182 J** |
| Solution density [C] | 0.033378 LOC/tok |
| Correctness/$ [C] | 9 |
| Quality/J [C] | 0.000097 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0250  |  **Energy:** ~6182J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_grgmkhc9/session.jsonl)
- [Generated code](./exp_grgmkhc9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1117 |
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
| Passed | 7 |
| Failed | 0 |
| Errors | 0 |
| Total | 7 |
| Pass rate | 100% |
| Duration | 6.4s |
