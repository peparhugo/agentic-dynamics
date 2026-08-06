# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:01:41

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0141, ~3546J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.718 |
| Architecture div | 0.833 |
| Structure div | 0.309 |
| Thinking ratio | 8.0% |
| Quality/$ | 81 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 475 |
| Cyclomatic complexity | 53.0 |
| Code quality | 0.211 |
| Novelty vs baseline | 0.972 |
| **Composite** | **0.511** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,209 |
| Completion tokens | 8,533 |
| Reasoning tokens | 1,631 |
| **Total tokens** | **20,373** |
| Thinking ratio | 8.0% |
| Output efficiency | 41.9% |
| Input cost | $0.002756 |
| Output cost | $0.009386 |
| Reasoning cost | $0.000228 |
| **Total cost** | **$0.014104** |
| **Total energy** | **~3546 J** |
| Solution density | 0.023315 LOC/tok |
| Correctness/$ | 65 |
| Quality/J | 0.000144 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0141  |  **Energy:** ~3546J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_p31ut41o/session.jsonl)
- [Generated code](./exp_p31ut41o/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 465 |
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
