# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:54:17

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.761

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.98, correctness=80%). Cost: $0.1685, ~4568J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.703 |
| Architecture div | 0.667 |
| Structure div | 0.470 |
| Thinking ratio | 8.3% |
| Quality/$ | 6 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 473 |
| Cyclomatic complexity | 91.0 |
| Code quality | 0.211 |
| Novelty vs baseline | 0.985 |
| **Composite** | **0.556** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 16,906 |
| Completion tokens | 9,143 |
| Reasoning tokens | 2,368 |
| **Total tokens** | **28,417** |
| Thinking ratio | 8.3% |
| Output efficiency | 32.2% |
| **Total cost** | **$0.168483** |
| **Total energy** | **~4568 J** |
| Solution density | 0.016645 LOC/tok |
| Correctness/$ | 53 |
| Quality/J | 0.000122 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.1685  |  **Energy:** ~4568J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_whigxsgm/session.jsonl)
- [Generated code](./exp_whigxsgm/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 448 |
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
