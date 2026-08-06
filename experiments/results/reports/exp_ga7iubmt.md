# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:22

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.795

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.77) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0350, ~10475J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.766 |
| Architecture div | 0.900 |
| Structure div | 0.383 |
| Thinking ratio | 25.4% |
| Quality/$ | 29 |
| Quality/J | 0.0001 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 947 |
| Cyclomatic complexity | 75.0 |
| Code quality | 0.106 |
| Novelty vs baseline | 0.971 |
| **Composite** | **0.560** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 16,270 |
| Completion tokens | 16,847 |
| Reasoning tokens | 11,273 |
| **Total tokens** | **44,390** |
| Thinking ratio | 25.4% |
| Output efficiency | 38.0% |
| **Total cost** | **$0.035030** |
| **Total energy** | **~10475 J** |
| Solution density | 0.021334 LOC/tok |
| Correctness/$ | 41 |
| Quality/J | 0.000053 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0350  |  **Energy:** ~10475J  |  **Thinking:** 25%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ga7iubmt/session.jsonl)
- [Generated code](./exp_ga7iubmt/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 11 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 926 |
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
