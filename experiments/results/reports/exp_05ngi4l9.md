# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:12:44

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.761

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0335, ~7688J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.749 |
| Architecture div [H] | 0.875 |
| Structure div [H] | 0.360 |
| Thinking ratio [C] | 7.2% |
| Quality/$ [C] | 30 |
| Quality/J [C] | 0.0001 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 809 |
| Cyclomatic complexity [C] | 64.0 |
| Code quality [H] | 0.124 |
| Novelty vs baseline [H] | 0.969 |
| **Composite [H]** | **0.536** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,562 |
| Completion tokens [M] | 19,835 |
| Reasoning tokens [M] | 3,151 |
| Cache read tokens [M] | 1,267,712 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **43,548** |
| Thinking ratio [C] | 7.2% |
| Output efficiency [C] | 45.5% |
| Input cost [M] | $0.000907 |
| Output cost [M] | $0.003564 |
| Reasoning cost [M] | $0.000072 |
| Cache cost [M] | $0.028994 |
| **Total cost** | **$0.033538** |
| **Total energy [X]** | **~7688 J** |
| Solution density [C] | 0.018577 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000070 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0335  |  **Energy:** ~7688J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_05ngi4l9/session.jsonl)
- [Generated code](./exp_05ngi4l9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| JS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1230 |
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
