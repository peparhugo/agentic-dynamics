# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:37:13

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.764

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0133, ~3176J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.718 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.280 |
| Thinking ratio [C] | 5.7% |
| Quality/$ [C] | 75 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 560 |
| Cyclomatic complexity [C] | 97.0 |
| Code quality [H] | 0.179 |
| Novelty vs baseline [H] | 0.972 |
| **Composite [H]** | **0.504** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,699 |
| Completion tokens [M] | 7,803 |
| Reasoning tokens [M] | 1,118 |
| Cache read tokens [M] | 233,088 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,620** |
| Thinking ratio [C] | 5.7% |
| Output efficiency [C] | 39.8% |
| Input cost [M] | $0.000865 |
| Output cost [M] | $0.002572 |
| Reasoning cost [M] | $0.000047 |
| Cache cost [M] | $0.009776 |
| **Total cost** | **$0.013260** |
| **Total energy [X]** | **~3176 J** |
| Solution density [C] | 0.028542 LOC/tok |
| Correctness/$ [C] | 18 |
| Quality/J [C] | 0.000159 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0133  |  **Energy:** ~3176J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_mp0le40h/session.jsonl)
- [Generated code](./exp_mp0le40h/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| JS files | 1 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 556 |
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
