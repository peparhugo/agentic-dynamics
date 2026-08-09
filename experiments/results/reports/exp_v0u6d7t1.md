# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:42:25

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.762

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0190, ~4656J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.750 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.389 |
| Thinking ratio [C] | 6.7% |
| Quality/$ [C] | 53 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 982 |
| Cyclomatic complexity [C] | 74.0 |
| Code quality [H] | 0.102 |
| Novelty vs baseline [H] | 0.968 |
| **Composite [H]** | **0.488** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 11,464 |
| Completion tokens [M] | 12,694 |
| Reasoning tokens [M] | 1,744 |
| Cache read tokens [M] | 400,768 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **25,902** |
| Thinking ratio [C] | 6.7% |
| Output efficiency [C] | 49.0% |
| Input cost [M] | $0.000801 |
| Output cost [M] | $0.003614 |
| Reasoning cost [M] | $0.000063 |
| Cache cost [M] | $0.014522 |
| **Total cost** | **$0.019001** |
| **Total energy [X]** | **~4656 J** |
| Solution density [C] | 0.037912 LOC/tok |
| Correctness/$ [C] | 11 |
| Quality/J [C] | 0.000105 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0190  |  **Energy:** ~4656J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_v0u6d7t1/session.jsonl)
- [Generated code](./exp_v0u6d7t1/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 21 |
| JS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1591 |
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
