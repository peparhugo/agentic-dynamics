# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:34:46

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.758

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0119, ~3022J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.718 |
| Architecture div [H] | 0.833 |
| Structure div [H] | 0.315 |
| Thinking ratio [C] | 8.6% |
| Quality/$ [C] | 84 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 650 |
| Cyclomatic complexity [C] | 109.0 |
| Code quality [H] | 0.154 |
| Novelty vs baseline [H] | 0.967 |
| **Composite [H]** | **0.541** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,243 |
| Completion tokens [M] | 6,847 |
| Reasoning tokens [M] | 1,506 |
| Cache read tokens [M] | 177,024 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **17,596** |
| Thinking ratio [C] | 8.6% |
| Output efficiency [C] | 38.9% |
| Input cost [M] | $0.000850 |
| Output cost [M] | $0.002566 |
| Reasoning cost [M] | $0.000072 |
| Cache cost [M] | $0.008442 |
| **Total cost** | **$0.011930** |
| **Total energy [X]** | **~3022 J** |
| Solution density [C] | 0.036940 LOC/tok |
| Correctness/$ [C] | 23 |
| Quality/J [C] | 0.000179 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0119  |  **Energy:** ~3022J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ih5ct7z5/session.jsonl)
- [Generated code](./exp_ih5ct7z5/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 641 |
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
