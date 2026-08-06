# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:34

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.898

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0058, ~1318J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.699 |
| Architecture div | 0.857 |
| Structure div | 0.220 |
| Thinking ratio | 5.3% |
| Quality/$ | 172 |
| Quality/J | 0.0008 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 364 |
| Cyclomatic complexity | 51.0 |
| Code quality | 0.275 |
| Novelty vs baseline | 0.967 |
| **Composite** | **0.636** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,093 |
| Completion tokens | 1,793 |
| Reasoning tokens | 549 |
| **Total tokens** | **10,435** |
| Thinking ratio | 5.3% |
| Output efficiency | 17.2% |
| **Total cost** | **$0.005801** |
| **Total energy** | **~1318 J** |
| Solution density | 0.034883 LOC/tok |
| Correctness/$ | 236 |
| Quality/J | 0.000482 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0058  |  **Energy:** ~1318J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_9vkw4hu4/session.jsonl)
- [Generated code](./exp_9vkw4hu4/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 357 |
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
