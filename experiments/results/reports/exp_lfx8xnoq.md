# Game Report: force_abandonment_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [force_abandonment_s0.5] process_perturbation_resample...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:05

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.747

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.59) with moderate resource use ($0.0161, ~6941J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 59.3% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 103 |
| Cyclomatic complexity [C] | 10.0 |
| Code quality [H] | 0.833 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.592** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6,900 |
| Completion tokens [M] | 1,812 |
| Reasoning tokens [M] | 12,707 |
| Cache read tokens [M] | 130,688 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **21,419** |
| Thinking ratio [C] | 59.3% |
| Output efficiency [C] | 8.5% |
| Input cost [M] | $0.002028 |
| Output cost [M] | $0.001597 |
| Reasoning cost [M] | $0.011202 |
| Cache cost [M] | $0.001280 |
| **Total cost** | **$0.016107** |
| **Total energy [X]** | **~6941 J** |
| Solution density [C] | 0.004809 LOC/tok |
| Correctness/$ [C] | 28 |
| Quality/J [C] | 0.000085 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0161  |  **Energy:** ~6941J  |  **Thinking:** 59%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_lfx8xnoq/session.jsonl)
- [Generated code](./exp_lfx8xnoq/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 103 |
| Functions | 12 |
| Classes | 2 |
| Functions/file | 3.0 |
| Classes/file | 0.5 |
| Avg lines/file | 26 |
| Type hints | 29% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 11 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
