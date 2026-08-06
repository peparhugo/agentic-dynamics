# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:41:52

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.761

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0335, ~7688J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.749 |
| Architecture div | 0.875 |
| Structure div | 0.360 |
| Thinking ratio | 7.2% |
| Quality/$ | 30 |
| Quality/J | 0.0001 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 809 |
| Cyclomatic complexity | 64.0 |
| Code quality | 0.124 |
| Novelty vs baseline | 0.969 |
| **Composite** | **0.536** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 20,562 |
| Completion tokens | 19,835 |
| Reasoning tokens | 3,151 |
| **Total tokens** | **43,548** |
| Thinking ratio | 7.2% |
| Output efficiency | 45.5% |
| **Total cost** | **$0.033538** |
| **Total energy** | **~7688 J** |
| Solution density | 0.018577 LOC/tok |
| Correctness/$ | 29 |
| Quality/J | 0.000070 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0335  |  **Energy:** ~7688J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_05ngi4l9/session.jsonl)
- [Generated code](./exp_05ngi4l9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| JS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1230 |
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
