# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:53:34

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.793

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0081, ~1918J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.718 |
| Architecture div | 1.000 |
| Structure div | 0.089 |
| Thinking ratio | 5.7% |
| Quality/$ | 123 |
| Quality/J | 0.0005 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 244 |
| Cyclomatic complexity | 29.0 |
| Code quality | 0.427 |
| Novelty vs baseline | 0.972 |
| **Composite** | **0.511** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,725 |
| Completion tokens | 3,766 |
| Reasoning tokens | 753 |
| **Total tokens** | **13,244** |
| Thinking ratio | 5.7% |
| Output efficiency | 28.4% |
| **Total cost** | **$0.008116** |
| **Total energy** | **~1918 J** |
| Solution density | 0.018423 LOC/tok |
| Correctness/$ | 121 |
| Quality/J | 0.000266 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0081  |  **Energy:** ~1918J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_uzrxy1t2/session.jsonl)
- [Generated code](./exp_uzrxy1t2/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 4 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 240 |
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
