# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:43:28

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.761

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0160, ~4067J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.742 |
| Architecture div | 0.857 |
| Structure div | 0.359 |
| Thinking ratio | 7.5% |
| Quality/$ | 63 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 861 |
| Cyclomatic complexity | 91.0 |
| Code quality | 0.116 |
| Novelty vs baseline | 0.972 |
| **Composite** | **0.535** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,219 |
| Completion tokens | 11,534 |
| Reasoning tokens | 1,610 |
| **Total tokens** | **21,363** |
| Thinking ratio | 7.5% |
| Output efficiency | 54.0% |
| **Total cost** | **$0.016000** |
| **Total energy** | **~4067 J** |
| Solution density | 0.040303 LOC/tok |
| Correctness/$ | 53 |
| Quality/J | 0.000131 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0160  |  **Energy:** ~4067J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_5d0kt9ne/session.jsonl)
- [Generated code](./exp_5d0kt9ne/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 11 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 836 |
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
