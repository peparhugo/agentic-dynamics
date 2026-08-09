# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** URL shortener with analytics and rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:42:52

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.66) with moderate resource use ($0.0103, ~2499J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 4.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 67% (4/6 constraints) |
| Lines of code [M] | 527 |
| Cyclomatic complexity [C] | 61.0 |
| Code quality [H] | 0.190 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.663** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,016 |
| Completion tokens [M] | 6,406 |
| Reasoning tokens [M] | 648 |
| Cache read tokens [M] | 74,624 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **16,070** |
| Thinking ratio [C] | 4.0% |
| Output efficiency [C] | 39.9% |
| Input cost [M] | $0.001256 |
| Output cost [M] | $0.003636 |
| Reasoning cost [M] | $0.000047 |
| Cache cost [M] | $0.005391 |
| **Total cost** | **$0.010329** |
| **Total energy [X]** | **~2499 J** |
| Solution density [C] | 0.032794 LOC/tok |
| Correctness/$ [C] | 50 |
| Quality/J [C] | 0.000265 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0103  |  **Energy:** ~2499J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_vx4gb129/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 527 |
| Functions | 6 |
| Classes | 6 |
| Functions/file | 0.8 |
| Classes/file | 0.8 |
| Avg lines/file | 66 |
| Type hints | 100% |
| Docstrings | 0% |
| Error handlers | 1 |
| Imports | 31 |
| Decorators | 0 |
| Test files | 1 |
| Test file rate | 12% |
| Parse errors | 0 |
