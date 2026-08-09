# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:23:52

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0141, ~3546J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.718 |
| Architecture div [H] | 0.833 |
| Structure div [H] | 0.309 |
| Thinking ratio [C] | 8.0% |
| Quality/$ [C] | 71 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 475 |
| Cyclomatic complexity [C] | 53.0 |
| Code quality [H] | 0.211 |
| Novelty vs baseline [H] | 0.972 |
| **Composite [H]** | **0.511** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,209 |
| Completion tokens [M] | 8,533 |
| Reasoning tokens [M] | 1,631 |
| Cache read tokens [M] | 226,432 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,373** |
| Thinking ratio [C] | 8.0% |
| Output efficiency [C] | 41.9% |
| Input cost [M] | $0.000882 |
| Output cost [M] | $0.003004 |
| Reasoning cost [M] | $0.000073 |
| Cache cost [M] | $0.010145 |
| **Total cost** | **$0.014104** |
| **Total energy [X]** | **~3546 J** |
| Solution density [C] | 0.023315 LOC/tok |
| Correctness/$ [C] | 18 |
| Quality/J [C] | 0.000144 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0141  |  **Energy:** ~3546J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_p31ut41o/session.jsonl)
- [Generated code](./exp_p31ut41o/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 465 |
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
