# Game Report: exp_37z0nq68-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT and tests...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:19:48

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.769

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.58) with moderate resource use ($0.0217, ~4993J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 3.2% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 796 |
| Cyclomatic complexity [C] | 117.0 |
| Code quality [H] | 0.126 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.579** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16,060 |
| Completion tokens [M] | 14,111 |
| Reasoning tokens [M] | 984 |
| Cache read tokens [M] | 439,424 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **31,155** |
| Thinking ratio [C] | 3.2% |
| Output efficiency [C] | 45.3% |
| Input cost [M] | $0.001155 |
| Output cost [M] | $0.004134 |
| Reasoning cost [M] | $0.000037 |
| Cache cost [M] | $0.016386 |
| **Total cost** | **$0.021712** |
| **Total energy [X]** | **~4993 J** |
| Solution density [C] | 0.025550 LOC/tok |
| Correctness/$ [C] | 12 |
| Quality/J [C] | 0.000116 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0217  |  **Energy:** ~4993J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_37z0nq68/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines (Py) | 796 |
| Functions | 85 |
| Classes | 14 |
| Functions/file | 9.4 |
| Classes/file | 1.6 |
| Avg lines/file | 88 |
| Type hints | 0% |
| Docstrings | 4% |
| Error handlers | 2 |
| Imports | 26 |
| Decorators | 19 |
| Test files | 3 |
| Test file rate | 33% |
| Parse errors | 0 |
