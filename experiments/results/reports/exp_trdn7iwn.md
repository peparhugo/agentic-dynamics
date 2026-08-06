# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:53:20

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.59) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $0.9862, ~2695J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.594 |
| Architecture div | 0.636 |
| Structure div | 0.177 |
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
| Lines of code | 633 |
| Cyclomatic complexity | 104.0 |
| Code quality | 0.158 |
| Novelty vs baseline | 0.954 |
| **Composite** | **0.540** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18 |
| Completion tokens | 11,709 |
| Reasoning tokens | 0 |
| **Total tokens** | **11,727** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| **Total cost** | **$0.986191** |
| **Total energy** | **~2695 J** |
| Solution density | 0.053978 LOC/tok |
| Correctness/$ | 62 |
| Quality/J | 0.000201 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.9862  |  **Energy:** ~2695J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_trdn7iwn/session.jsonl)
- [Generated code](./exp_trdn7iwn/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 622 |
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
