# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:26:10

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.793

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0081, ~1918J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.718 |
| Architecture div [H] | 1.000 |
| Structure div [H] | 0.089 |
| Thinking ratio [C] | 5.7% |
| Quality/$ [C] | 123 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 244 |
| Cyclomatic complexity [C] | 29.0 |
| Code quality [H] | 0.427 |
| Novelty vs baseline [H] | 0.972 |
| **Composite [H]** | **0.511** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,725 |
| Completion tokens [M] | 3,766 |
| Reasoning tokens [M] | 753 |
| Cache read tokens [M] | 107,264 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **13,244** |
| Thinking ratio [C] | 5.7% |
| Output efficiency [C] | 28.4% |
| Input cost [M] | $0.000884 |
| Output cost [M] | $0.001555 |
| Reasoning cost [M] | $0.000040 |
| Cache cost [M] | $0.005637 |
| **Total cost** | **$0.008116** |
| **Total energy [X]** | **~1918 J** |
| Solution density [C] | 0.018423 LOC/tok |
| Correctness/$ [C] | 37 |
| Quality/J [C] | 0.000266 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0081  |  **Energy:** ~1918J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_uzrxy1t2/session.jsonl)
- [Generated code](./exp_uzrxy1t2/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 4 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 240 |
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
