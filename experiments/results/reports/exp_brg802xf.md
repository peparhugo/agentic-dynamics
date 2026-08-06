# Game Report: invert_constraint_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:47:09

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.765

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.68) and found a novel correct solution (novelty=0.98, correctness=80%). Cost: $0.1849, ~5284J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.675 |
| Architecture div | 0.600 |
| Structure div | 0.467 |
| Thinking ratio | 6.1% |
| Quality/$ | 5 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 476 |
| Cyclomatic complexity | 76.0 |
| Code quality | 0.210 |
| Novelty vs baseline | 0.984 |
| **Composite** | **0.512** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 26,522 |
| Completion tokens | 9,040 |
| Reasoning tokens | 2,304 |
| **Total tokens** | **37,866** |
| Thinking ratio | 6.1% |
| Output efficiency | 23.9% |
| **Total cost** | **$0.184944** |
| **Total energy** | **~5284 J** |
| Solution density | 0.012571 LOC/tok |
| Correctness/$ | 46 |
| Quality/J | 0.000097 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.1849  |  **Energy:** ~5284J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_brg802xf/session.jsonl)
- [Generated code](./exp_brg802xf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 443 |
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
