# Game Report: standardized_retry-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [standardized_retry] gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:15:47

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.810

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.63) with moderate resource use ($0.6610, ~1549J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.449 |
| Architecture div [H] | 0.333 |
| Structure div [H] | 0.200 |
| Thinking ratio [C] | 8.9% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0006 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 322 |
| Cyclomatic complexity [C] | 46.0 |
| Code quality [H] | 0.311 |
| Novelty vs baseline [H] | 0.853 |
| **Composite [H]** | **0.626** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 39 |
| Completion tokens [M] | 5,595 |
| Reasoning tokens [M] | 551 |
| Cache read tokens [M] | 123,920 |
| Cache write tokens [M] | 13,437 |
| **Total tokens** | **6,185** |
| Thinking ratio [C] | 8.9% |
| Output efficiency [C] | 90.5% |
| Input cost [M] | $0.000187 |
| Output cost [M] | $0.214341 |
| Reasoning cost [M] | $0.021108 |
| Cache cost [M] | $0.425397 |
| **Total cost** | **$0.661033** |
| **Total energy [X]** | **~1549 J** |
| Solution density [C] | 0.052061 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000404 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.6610  |  **Energy:** ~1549J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp__l_pm4_4/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 322 |
| Functions | 29 |
| Classes | 1 |
| Functions/file | 14.5 |
| Classes/file | 0.5 |
| Avg lines/file | 161 |
| Type hints | 36% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 15 |
| Decorators | 8 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |
