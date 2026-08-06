# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:42:34

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.821

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.76) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0279, ~7340J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.760 |
| Architecture div | 0.875 |
| Structure div | 0.395 |
| Thinking ratio | 12.4% |
| Quality/$ | 36 |
| Quality/J | 0.0001 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 1275 |
| Cyclomatic complexity | 95.0 |
| Code quality | 0.078 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.597** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 11,866 |
| Completion tokens | 18,899 |
| Reasoning tokens | 4,349 |
| **Total tokens** | **35,114** |
| Thinking ratio | 12.4% |
| Output efficiency | 53.8% |
| **Total cost** | **$0.027914** |
| **Total energy** | **~7340 J** |
| Solution density | 0.036310 LOC/tok |
| Correctness/$ | 41 |
| Quality/J | 0.000081 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0279  |  **Energy:** ~7340J  |  **Thinking:** 12%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_2yyxp_8_/session.jsonl)
- [Generated code](./exp_2yyxp_8_/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 15 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1265 |
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
