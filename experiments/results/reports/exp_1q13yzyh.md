# Game Report: invert_constraint_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:42:15

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.63) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $0.9285, ~2109J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.629 |
| Architecture div | 0.750 |
| Structure div | 0.144 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0005 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 485 |
| Cyclomatic complexity | 65.0 |
| Code quality | 0.206 |
| Novelty vs baseline | 0.954 |
| **Composite** | **0.577** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10 |
| Completion tokens | 9,167 |
| Reasoning tokens | 0 |
| **Total tokens** | **9,177** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$0.928507** |
| **Total energy** | **~2109 J** |
| Solution density | 0.052850 LOC/tok |
| Correctness/$ | 99 |
| Quality/J | 0.000274 |

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
