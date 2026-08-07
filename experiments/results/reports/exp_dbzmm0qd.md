# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:19:05

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.753

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0133, ~3394J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.696 |
| Architecture div [H] | 0.833 |
| Structure div [H] | 0.243 |
| Thinking ratio [C] | 11.2% |
| Quality/$ [C] | 75 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 439 |
| Cyclomatic complexity [C] | 48.0 |
| Code quality [H] | 0.228 |
| Novelty vs baseline [H] | 0.967 |
| **Composite [H]** | **0.513** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,178 |
| Completion tokens [M] | 6,817 |
| Reasoning tokens [M] | 2,152 |
| Cache read tokens [M] | 288,768 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,147** |
| Thinking ratio [C] | 11.2% |
| Output efficiency [C] | 35.6% |
| Input cost [M] | $0.000716 |
| Output cost [M] | $0.001953 |
| Reasoning cost [M] | $0.000078 |
| Cache cost [M] | $0.010530 |
| **Total cost** | **$0.013277** |
| **Total energy [X]** | **~3394 J** |
| Solution density [C] | 0.022928 LOC/tok |
| Correctness/$ [C] | 16 |
| Quality/J [C] | 0.000151 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0133  |  **Energy:** ~3394J  |  **Thinking:** 11%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_dbzmm0qd/session.jsonl)
- [Generated code](./exp_dbzmm0qd/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 430 |
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
