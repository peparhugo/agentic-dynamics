# Game Report: exp_mmp26p5c-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API: JWT, pagination, rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:36:56

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.768

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0148, ~3606J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 3.5% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 756 |
| Cyclomatic complexity [C] | 46.0 |
| Code quality [H] | 0.132 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.751** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,181 |
| Completion tokens [M] | 10,981 |
| Reasoning tokens [M] | 737 |
| Cache read tokens [M] | 164,864 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,899** |
| Thinking ratio [C] | 3.5% |
| Output efficiency [C] | 52.5% |
| Input cost [M] | $0.000971 |
| Output cost [M] | $0.004732 |
| Reasoning cost [M] | $0.000040 |
| Cache cost [M] | $0.009042 |
| **Total cost** | **$0.014786** |
| **Total energy [X]** | **~3606 J** |
| Solution density [C] | 0.036174 LOC/tok |
| Correctness/$ [C] | 26 |
| Quality/J [C] | 0.000208 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0148  |  **Energy:** ~3606J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_mmp26p5c/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 21 |
| Total lines (Py) | 756 |
| Functions | 72 |
| Classes | 21 |
| Functions/file | 3.4 |
| Classes/file | 1.0 |
| Avg lines/file | 36 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 42 |
| Decorators | 30 |
| Test files | 4 |
| Test file rate | 19% |
| Parse errors | 0 |
