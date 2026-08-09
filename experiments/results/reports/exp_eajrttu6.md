# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:31:11

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.837

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0134, ~3040J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.723 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.299 |
| Thinking ratio [C] | 4.0% |
| Quality/$ [C] | 75 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 615 |
| Cyclomatic complexity [C] | 93.0 |
| Code quality [H] | 0.163 |
| Novelty vs baseline [H] | 0.968 |
| **Composite [H]** | **0.571** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,603 |
| Completion tokens [M] | 7,933 |
| Reasoning tokens [M] | 782 |
| Cache read tokens [M] | 325,120 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,318** |
| Thinking ratio [C] | 4.0% |
| Output efficiency [C] | 41.1% |
| Input cost [M] | $0.000669 |
| Output cost [M] | $0.002040 |
| Reasoning cost [M] | $0.000026 |
| Cache cost [M] | $0.010639 |
| **Total cost** | **$0.013373** |
| **Total energy [X]** | **~3040 J** |
| Solution density [C] | 0.031836 LOC/tok |
| Correctness/$ [C] | 17 |
| Quality/J [C] | 0.000188 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0134  |  **Energy:** ~3040J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_eajrttu6/session.jsonl)
- [Generated code](./exp_eajrttu6/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 604 |
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
