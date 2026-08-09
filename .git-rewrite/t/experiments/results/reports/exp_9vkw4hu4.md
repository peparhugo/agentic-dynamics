# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:15:34

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.898

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0058, ~1318J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.699 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.220 |
| Thinking ratio [C] | 5.3% |
| Quality/$ [C] | 172 |
| Quality/J [C] | 0.0008 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 364 |
| Cyclomatic complexity [C] | 51.0 |
| Code quality [H] | 0.275 |
| Novelty vs baseline [H] | 0.967 |
| **Composite [H]** | **0.636** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,093 |
| Completion tokens [M] | 1,793 |
| Reasoning tokens [M] | 549 |
| Cache read tokens [M] | 67,072 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **10,435** |
| Thinking ratio [C] | 5.3% |
| Output efficiency [C] | 17.2% |
| Input cost [M] | $0.000930 |
| Output cost [M] | $0.000840 |
| Reasoning cost [M] | $0.000033 |
| Cache cost [M] | $0.003998 |
| **Total cost** | **$0.005801** |
| **Total energy [X]** | **~1318 J** |
| Solution density [C] | 0.034883 LOC/tok |
| Correctness/$ [C] | 73 |
| Quality/J [C] | 0.000482 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0058  |  **Energy:** ~1318J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_9vkw4hu4/session.jsonl)
- [Generated code](./exp_9vkw4hu4/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 357 |
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
