# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:35:49

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.756

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0168, ~4508J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.738 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.350 |
| Thinking ratio [C] | 9.7% |
| Quality/$ [C] | 59 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 921 |
| Cyclomatic complexity [C] | 45.0 |
| Code quality [H] | 0.109 |
| Novelty vs baseline [H] | 0.968 |
| **Composite [H]** | **0.533** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,021 |
| Completion tokens [M] | 11,870 |
| Reasoning tokens [M] | 2,248 |
| Cache read tokens [M] | 167,296 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,139** |
| Thinking ratio [C] | 9.7% |
| Output efficiency [C] | 51.3% |
| Input cost [M] | $0.001044 |
| Output cost [M] | $0.005596 |
| Reasoning cost [M] | $0.000135 |
| Cache cost [M] | $0.010038 |
| **Total cost** | **$0.016813** |
| **Total energy [X]** | **~4508 J** |
| Solution density [C] | 0.039803 LOC/tok |
| Correctness/$ [C] | 20 |
| Quality/J [C] | 0.000118 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0168  |  **Energy:** ~4508J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_wmysu1lk/session.jsonl)
- [Generated code](./exp_wmysu1lk/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 16 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 897 |
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
