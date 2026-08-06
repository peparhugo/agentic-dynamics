# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:13

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.746

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.99, correctness=80%). Cost: $0.2067, ~6159J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.724 |
| Architecture div | 0.714 |
| Structure div | 0.473 |
| Thinking ratio | 15.9% |
| Quality/$ | 5 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 525 |
| Cyclomatic complexity | 89.0 |
| Code quality | 0.190 |
| Novelty vs baseline | 0.986 |
| **Composite** | **0.552** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18,710 |
| Completion tokens | 9,414 |
| Reasoning tokens | 5,312 |
| **Total tokens** | **33,436** |
| Thinking ratio | 15.9% |
| Output efficiency | 28.2% |
| **Total cost** | **$0.206743** |
| **Total energy** | **~6159 J** |
| Solution density | 0.015702 LOC/tok |
| Correctness/$ | 50 |
| Quality/J | 0.000090 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.2067  |  **Energy:** ~6159J  |  **Thinking:** 16%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_9i_wq5gc/session.jsonl)
- [Generated code](./exp_9i_wq5gc/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 495 |
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
