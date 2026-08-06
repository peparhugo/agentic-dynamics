# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:54:35

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.756

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0168, ~4508J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.738 |
| Architecture div | 0.857 |
| Structure div | 0.350 |
| Thinking ratio | 9.7% |
| Quality/$ | 59 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 921 |
| Cyclomatic complexity | 45.0 |
| Code quality | 0.109 |
| Novelty vs baseline | 0.968 |
| **Composite** | **0.533** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,021 |
| Completion tokens | 11,870 |
| Reasoning tokens | 2,248 |
| **Total tokens** | **23,139** |
| Thinking ratio | 9.7% |
| Output efficiency | 51.3% |
| **Total cost** | **$0.016813** |
| **Total energy** | **~4508 J** |
| Solution density | 0.039803 LOC/tok |
| Correctness/$ | 51 |
| Quality/J | 0.000118 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0168  |  **Energy:** ~4508J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_wmysu1lk/session.jsonl)
- [Generated code](./exp_wmysu1lk/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 16 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 897 |
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
