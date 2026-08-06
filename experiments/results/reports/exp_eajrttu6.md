# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:52:47

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.837

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.72) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0134, ~3040J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.723 |
| Architecture div | 0.857 |
| Structure div | 0.299 |
| Thinking ratio | 4.0% |
| Quality/$ | 85 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 615 |
| Cyclomatic complexity | 93.0 |
| Code quality | 0.163 |
| Novelty vs baseline | 0.968 |
| **Composite** | **0.613** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,603 |
| Completion tokens | 7,933 |
| Reasoning tokens | 782 |
| **Total tokens** | **19,318** |
| Thinking ratio | 4.0% |
| Output efficiency | 41.1% |
| Input cost | $0.002863 |
| Output cost | $0.008726 |
| Reasoning cost | $0.000109 |
| **Total cost** | **$0.013373** |
| **Total energy** | **~3040 J** |
| Solution density | 0.031836 LOC/tok |
| Correctness/$ | 85 |
| Quality/J | 0.000202 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0134  |  **Energy:** ~3040J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_eajrttu6/session.jsonl)
- [Generated code](./exp_eajrttu6/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 604 |
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
