# Game Report: exp_wo0bkk9m-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** Authenticated REST API with JWT...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:36:18

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.6322, ~1586J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0006 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 298 |
| Cyclomatic complexity [C] | 41.0 |
| Code quality [H] | 0.336 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.749** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12 |
| Completion tokens [M] | 6,893 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 66,294 |
| Cache write tokens [M] | 17,692 |
| **Total tokens** | **6,905** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000120 |
| Output cost [M] | $0.344650 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.287444 |
| **Total cost** | **$0.632214** |
| **Total energy [X]** | **~1586 J** |
| Solution density [C] | 0.043157 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000472 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.6322  |  **Energy:** ~1586J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_wo0bkk9m/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 298 |
| Functions | 29 |
| Classes | 17 |
| Functions/file | 4.1 |
| Classes/file | 2.4 |
| Avg lines/file | 43 |
| Type hints | 53% |
| Docstrings | 14% |
| Error handlers | 6 |
| Imports | 19 |
| Decorators | 10 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
