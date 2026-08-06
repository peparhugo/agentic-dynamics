# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:51:25

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.753

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0133, ~3394J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.696 |
| Architecture div | 0.833 |
| Structure div | 0.243 |
| Thinking ratio | 11.2% |
| Quality/$ | 95 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 439 |
| Cyclomatic complexity | 48.0 |
| Code quality | 0.228 |
| Novelty vs baseline | 0.967 |
| **Composite** | **0.513** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,178 |
| Completion tokens | 6,817 |
| Reasoning tokens | 2,152 |
| **Total tokens** | **19,147** |
| Thinking ratio | 11.2% |
| Output efficiency | 35.6% |
| Input cost | $0.002748 |
| Output cost | $0.007499 |
| Reasoning cost | $0.000301 |
| **Total cost** | **$0.013277** |
| **Total energy** | **~3394 J** |
| Solution density | 0.022928 LOC/tok |
| Correctness/$ | 76 |
| Quality/J | 0.000151 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0133  |  **Energy:** ~3394J  |  **Thinking:** 11%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_dbzmm0qd/session.jsonl)
- [Generated code](./exp_dbzmm0qd/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 430 |
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
