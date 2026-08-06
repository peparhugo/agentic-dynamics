# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:53:37

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.762

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0190, ~4656J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.750 |
| Architecture div | 0.857 |
| Structure div | 0.389 |
| Thinking ratio | 6.7% |
| Quality/$ | 53 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 982 |
| Cyclomatic complexity | 74.0 |
| Code quality | 0.102 |
| Novelty vs baseline | 0.968 |
| **Composite** | **0.488** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 11,464 |
| Completion tokens | 12,694 |
| Reasoning tokens | 1,744 |
| **Total tokens** | **25,902** |
| Thinking ratio | 6.7% |
| Output efficiency | 49.0% |
| **Total cost** | **$0.019001** |
| **Total energy** | **~4656 J** |
| Solution density | 0.037912 LOC/tok |
| Correctness/$ | 46 |
| Quality/J | 0.000105 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0190  |  **Energy:** ~4656J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_v0u6d7t1/session.jsonl)
- [Generated code](./exp_v0u6d7t1/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 21 |
| JS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1591 |
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
