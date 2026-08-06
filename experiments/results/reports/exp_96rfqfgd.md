# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:10

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.726

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0151, ~4899J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.739 |
| Architecture div | 0.857 |
| Structure div | 0.351 |
| Thinking ratio | 24.6% |
| Quality/$ | 66 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 713 |
| Cyclomatic complexity | 60.0 |
| Code quality | 0.140 |
| Novelty vs baseline | 0.971 |
| **Composite** | **0.497** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 6,588 |
| Completion tokens | 8,760 |
| Reasoning tokens | 5,015 |
| **Total tokens** | **20,363** |
| Thinking ratio | 24.6% |
| Output efficiency | 43.0% |
| **Total cost** | **$0.015082** |
| **Total energy** | **~4899 J** |
| Solution density | 0.035014 LOC/tok |
| Correctness/$ | 66 |
| Quality/J | 0.000101 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0151  |  **Energy:** ~4899J  |  **Thinking:** 25%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_96rfqfgd/session.jsonl)
- [Generated code](./exp_96rfqfgd/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 690 |
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
