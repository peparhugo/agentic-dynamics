# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:21:17

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.761

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0160, ~4067J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.742 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.359 |
| Thinking ratio [C] | 7.5% |
| Quality/$ [C] | 63 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 861 |
| Cyclomatic complexity [C] | 91.0 |
| Code quality [H] | 0.116 |
| Novelty vs baseline [H] | 0.972 |
| **Composite [H]** | **0.535** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,219 |
| Completion tokens [M] | 11,534 |
| Reasoning tokens [M] | 1,610 |
| Cache read tokens [M] | 272,896 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **21,363** |
| Thinking ratio [C] | 7.5% |
| Output efficiency [C] | 54.0% |
| Input cost [M] | $0.000666 |
| Output cost [M] | $0.003806 |
| Reasoning cost [M] | $0.000068 |
| Cache cost [M] | $0.011461 |
| **Total cost** | **$0.016000** |
| **Total energy [X]** | **~4067 J** |
| Solution density [C] | 0.040303 LOC/tok |
| Correctness/$ [C] | 15 |
| Quality/J [C] | 0.000131 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0160  |  **Energy:** ~4067J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_5d0kt9ne/session.jsonl)
- [Generated code](./exp_5d0kt9ne/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 11 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 836 |
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
