# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:40

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.828

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0250, ~6182J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.751 |
| Architecture div | 0.857 |
| Structure div | 0.392 |
| Thinking ratio | 8.9% |
| Quality/$ | 40 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 1133 |
| Cyclomatic complexity | 127.0 |
| Code quality | 0.088 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.599** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 15,688 |
| Completion tokens | 15,224 |
| Reasoning tokens | 3,033 |
| **Total tokens** | **33,945** |
| Thinking ratio | 8.9% |
| Output efficiency | 44.8% |
| **Total cost** | **$0.025030** |
| **Total energy** | **~6182 J** |
| Solution density | 0.033378 LOC/tok |
| Correctness/$ | 47 |
| Quality/J | 0.000097 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0250  |  **Energy:** ~6182J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_grgmkhc9/session.jsonl)
- [Generated code](./exp_grgmkhc9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1117 |
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
