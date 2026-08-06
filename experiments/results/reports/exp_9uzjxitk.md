# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:31

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.751

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0237, ~6428J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.755 |
| Architecture div | 0.875 |
| Structure div | 0.378 |
| Thinking ratio | 12.3% |
| Quality/$ | 42 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 841 |
| Cyclomatic complexity | 91.0 |
| Code quality | 0.119 |
| Novelty vs baseline | 0.971 |
| **Composite** | **0.492** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 13,799 |
| Completion tokens | 14,939 |
| Reasoning tokens | 4,018 |
| **Total tokens** | **32,756** |
| Thinking ratio | 12.3% |
| Output efficiency | 45.6% |
| **Total cost** | **$0.023686** |
| **Total energy** | **~6428 J** |
| Solution density | 0.025675 LOC/tok |
| Correctness/$ | 39 |
| Quality/J | 0.000077 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0237  |  **Energy:** ~6428J  |  **Thinking:** 12%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_9uzjxitk/session.jsonl)
- [Generated code](./exp_9uzjxitk/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 21 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1292 |
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
