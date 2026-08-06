# Game Report: shift_framing_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:43:57

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.63) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $1.0062, ~2650J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.627 |
| Architecture div | 0.727 |
| Structure div | 0.167 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 678 |
| Cyclomatic complexity | 105.0 |
| Code quality | 0.147 |
| Novelty vs baseline | 0.955 |
| **Composite** | **0.538** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 22 |
| Completion tokens | 11,516 |
| Reasoning tokens | 0 |
| **Total tokens** | **11,538** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| **Total cost** | **$1.006182** |
| **Total energy** | **~2650 J** |
| Solution density | 0.058762 LOC/tok |
| Correctness/$ | 63 |
| Quality/J | 0.000203 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $1.0062  |  **Energy:** ~2650J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_73hs5n35/session.jsonl)
- [Generated code](./exp_73hs5n35/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 666 |
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
