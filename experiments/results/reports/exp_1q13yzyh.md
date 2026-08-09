# Game Report: invert_constraint_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:18:14

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.63) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $0.9285, ~2109J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.629 |
| Architecture div [H] | 0.750 |
| Structure div [H] | 0.144 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 485 |
| Cyclomatic complexity [C] | 65.0 |
| Code quality [H] | 0.206 |
| Novelty vs baseline [H] | 0.954 |
| **Composite [H]** | **0.577** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10 |
| Completion tokens [M] | 9,167 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 42,182 |
| Cache write tokens [M] | 34,230 |
| **Total tokens** | **9,177** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000100 |
| Output cost [M] | $0.458350 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.470057 |
| **Total cost** | **$0.928507** |
| **Total energy [X]** | **~2109 J** |
| Solution density [C] | 0.052850 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000274 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.9285  |  **Energy:** ~2109J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_1q13yzyh/session.jsonl)
- [Generated code](./exp_1q13yzyh/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 6 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 474 |
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
