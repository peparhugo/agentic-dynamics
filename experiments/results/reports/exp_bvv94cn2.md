# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:50:32

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.757

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0243, ~6268J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.754 |
| Architecture div | 0.857 |
| Structure div | 0.401 |
| Thinking ratio | 9.2% |
| Quality/$ | 46 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 1115 |
| Cyclomatic complexity | 113.0 |
| Code quality | 0.090 |
| Novelty vs baseline | 0.968 |
| **Composite** | **0.572** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 14,532 |
| Completion tokens | 15,893 |
| Reasoning tokens | 3,085 |
| **Total tokens** | **33,510** |
| Thinking ratio | 9.2% |
| Output efficiency | 47.4% |
| Input cost | $0.003924 |
| Output cost | $0.017482 |
| Reasoning cost | $0.000432 |
| **Total cost** | **$0.024283** |
| **Total energy** | **~6268 J** |
| Solution density | 0.033274 LOC/tok |
| Correctness/$ | 37 |
| Quality/J | 0.000091 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0243  |  **Energy:** ~6268J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_bvv94cn2/session.jsonl)
- [Generated code](./exp_bvv94cn2/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1078 |
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
