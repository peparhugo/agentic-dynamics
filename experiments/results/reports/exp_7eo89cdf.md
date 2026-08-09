# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:22:29

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0236, ~5484J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.735 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.341 |
| Thinking ratio [C] | 7.6% |
| Quality/$ [C] | 42 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 632 |
| Cyclomatic complexity [C] | 59.0 |
| Code quality [H] | 0.158 |
| Novelty vs baseline [H] | 0.966 |
| **Composite [H]** | **0.499** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16,931 |
| Completion tokens [M] | 12,948 |
| Reasoning tokens [M] | 2,450 |
| Cache read tokens [M] | 792,320 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **32,329** |
| Thinking ratio [C] | 7.6% |
| Output efficiency [C] | 40.1% |
| Input cost [M] | $0.000831 |
| Output cost [M] | $0.002588 |
| Reasoning cost [M] | $0.000062 |
| Cache cost [M] | $0.020153 |
| **Total cost** | **$0.023633** |
| **Total energy [X]** | **~5484 J** |
| Solution density [C] | 0.019549 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000091 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0236  |  **Energy:** ~5484J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_7eo89cdf/session.jsonl)
- [Generated code](./exp_7eo89cdf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 15 |
| JS files | 6 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1009 |
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
