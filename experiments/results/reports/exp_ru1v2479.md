# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:52:48

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.815

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0188, ~5303J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.732 |
| Architecture div | 0.857 |
| Structure div | 0.327 |
| Thinking ratio | 14.9% |
| Quality/$ | 53 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 758 |
| Cyclomatic complexity | 67.0 |
| Code quality | 0.132 |
| Novelty vs baseline | 0.969 |
| **Composite** | **0.607** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,331 |
| Completion tokens | 11,601 |
| Reasoning tokens | 3,847 |
| **Total tokens** | **25,779** |
| Thinking ratio | 14.9% |
| Output efficiency | 45.0% |
| **Total cost** | **$0.018840** |
| **Total energy** | **~5303 J** |
| Solution density | 0.029404 LOC/tok |
| Correctness/$ | 62 |
| Quality/J | 0.000115 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0188  |  **Energy:** ~5303J  |  **Thinking:** 15%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ru1v2479/session.jsonl)
- [Generated code](./exp_ru1v2479/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 20 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1246 |
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
