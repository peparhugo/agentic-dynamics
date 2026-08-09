# Game Report: exp_s73ost4b-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API with JWT, pagination, rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:40:25

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.770

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0167, ~3890J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 2.5% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 899 |
| Cyclomatic complexity [C] | 83.0 |
| Code quality [H] | 0.111 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.747** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,342 |
| Completion tokens [M] | 12,536 |
| Reasoning tokens [M] | 552 |
| Cache read tokens [M] | 357,376 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,430** |
| Thinking ratio [C] | 2.5% |
| Output efficiency [C] | 55.9% |
| Input cost [M] | $0.000636 |
| Output cost [M] | $0.003477 |
| Reasoning cost [M] | $0.000019 |
| Cache cost [M] | $0.012614 |
| **Total cost** | **$0.016746** |
| **Total energy [X]** | **~3890 J** |
| Solution density [C] | 0.040080 LOC/tok |
| Correctness/$ [C] | 15 |
| Quality/J [C] | 0.000192 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0167  |  **Energy:** ~3890J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_s73ost4b/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 21 |
| Total lines (Py) | 899 |
| Functions | 105 |
| Classes | 18 |
| Functions/file | 5.0 |
| Classes/file | 0.9 |
| Avg lines/file | 43 |
| Type hints | 3% |
| Docstrings | 0% |
| Error handlers | 13 |
| Imports | 66 |
| Decorators | 72 |
| Test files | 8 |
| Test file rate | 38% |
| Parse errors | 0 |
