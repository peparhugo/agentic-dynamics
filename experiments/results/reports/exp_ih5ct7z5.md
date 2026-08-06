# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:49:22

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.758

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0119, ~3022J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.718 |
| Architecture div | 0.833 |
| Structure div | 0.315 |
| Thinking ratio | 8.6% |
| Quality/$ | 84 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 650 |
| Cyclomatic complexity | 109.0 |
| Code quality | 0.154 |
| Novelty vs baseline | 0.967 |
| **Composite** | **0.541** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,243 |
| Completion tokens | 6,847 |
| Reasoning tokens | 1,506 |
| **Total tokens** | **17,596** |
| Thinking ratio | 8.6% |
| Output efficiency | 38.9% |
| **Total cost** | **$0.011930** |
| **Total energy** | **~3022 J** |
| Solution density | 0.036940 LOC/tok |
| Correctness/$ | 78 |
| Quality/J | 0.000179 |

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
