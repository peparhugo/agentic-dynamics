# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:01

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.764

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0133, ~3176J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.718 |
| Architecture div | 0.857 |
| Structure div | 0.280 |
| Thinking ratio | 5.7% |
| Quality/$ | 75 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 560 |
| Cyclomatic complexity | 97.0 |
| Code quality | 0.179 |
| Novelty vs baseline | 0.972 |
| **Composite** | **0.504** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,699 |
| Completion tokens | 7,803 |
| Reasoning tokens | 1,118 |
| **Total tokens** | **19,620** |
| Thinking ratio | 5.7% |
| Output efficiency | 39.8% |
| **Total cost** | **$0.013260** |
| **Total energy** | **~3176 J** |
| Solution density | 0.028542 LOC/tok |
| Correctness/$ | 69 |
| Quality/J | 0.000159 |

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
