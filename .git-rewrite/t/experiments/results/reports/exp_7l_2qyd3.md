# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:15:01

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.77) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0200, ~5136J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.768 |
| Architecture div [H] | 0.900 |
| Structure div [H] | 0.392 |
| Thinking ratio [C] | 7.8% |
| Quality/$ [C] | 50 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 1048 |
| Cyclomatic complexity [C] | 69.0 |
| Code quality [H] | 0.095 |
| Novelty vs baseline [H] | 0.970 |
| **Composite [H]** | **0.487** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 14,993 |
| Completion tokens [M] | 12,367 |
| Reasoning tokens [M] | 2,324 |
| Cache read tokens [M] | 202,496 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **29,684** |
| Thinking ratio [C] | 7.8% |
| Output efficiency [C] | 41.7% |
| Input cost [M] | $0.001751 |
| Output cost [M] | $0.005884 |
| Reasoning cost [M] | $0.000141 |
| Cache cost [M] | $0.012262 |
| **Total cost** | **$0.020037** |
| **Total energy [X]** | **~5136 J** |
| Solution density [C] | 0.035305 LOC/tok |
| Correctness/$ [C] | 17 |
| Quality/J [C] | 0.000095 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0200  |  **Energy:** ~5136J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_7l_2qyd3/session.jsonl)
- [Generated code](./exp_7l_2qyd3/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 14 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1035 |
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
