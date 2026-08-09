# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:25:24

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.815

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0188, ~5303J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.732 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.327 |
| Thinking ratio [C] | 14.9% |
| Quality/$ [C] | 53 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 758 |
| Cyclomatic complexity [C] | 67.0 |
| Code quality [H] | 0.132 |
| Novelty vs baseline [H] | 0.969 |
| **Composite [H]** | **0.607** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,331 |
| Completion tokens [M] | 11,601 |
| Reasoning tokens [M] | 3,847 |
| Cache read tokens [M] | 250,112 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **25,779** |
| Thinking ratio [C] | 14.9% |
| Output efficiency [C] | 45.0% |
| Input cost [M] | $0.001028 |
| Output cost [M] | $0.004705 |
| Reasoning cost [M] | $0.000199 |
| Cache cost [M] | $0.012909 |
| **Total cost** | **$0.018840** |
| **Total energy [X]** | **~5303 J** |
| Solution density [C] | 0.029404 LOC/tok |
| Correctness/$ [C] | 20 |
| Quality/J [C] | 0.000115 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0188  |  **Energy:** ~5303J  |  **Thinking:** 15%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ru1v2479/session.jsonl)
- [Generated code](./exp_ru1v2479/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 20 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1246 |
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
