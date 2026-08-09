# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:18:55

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.757

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0243, ~6268J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.754 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.401 |
| Thinking ratio [C] | 9.2% |
| Quality/$ [C] | 41 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 1115 |
| Cyclomatic complexity [C] | 113.0 |
| Code quality [H] | 0.090 |
| Novelty vs baseline [H] | 0.968 |
| **Composite [H]** | **0.529** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 14,532 |
| Completion tokens [M] | 15,893 |
| Reasoning tokens [M] | 3,085 |
| Cache read tokens [M] | 400,256 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **33,510** |
| Thinking ratio [C] | 9.2% |
| Output efficiency [C] | 47.4% |
| Input cost [M] | $0.001224 |
| Output cost [M] | $0.005451 |
| Reasoning cost [M] | $0.000135 |
| Cache cost [M] | $0.017474 |
| **Total cost** | **$0.024283** |
| **Total energy [X]** | **~6268 J** |
| Solution density [C] | 0.033274 LOC/tok |
| Correctness/$ [C] | 10 |
| Quality/J [C] | 0.000084 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0243  |  **Energy:** ~6268J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_bvv94cn2/session.jsonl)
- [Generated code](./exp_bvv94cn2/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1078 |
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
