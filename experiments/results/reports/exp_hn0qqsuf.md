# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:forced-silent] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:34:01

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0159, ~4065J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 5.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 726 |
| Cyclomatic complexity [C] | 72.0 |
| Code quality [H] | 0.138 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.753** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,057 |
| Completion tokens [M] | 11,544 |
| Reasoning tokens [M] | 1,288 |
| Cache read tokens [M] | 98,944 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,889** |
| Thinking ratio [C] | 5.6% |
| Output efficiency [C] | 50.4% |
| Input cost [M] | $0.001466 |
| Output cost [M] | $0.006856 |
| Reasoning cost [M] | $0.000097 |
| Cache cost [M] | $0.007478 |
| **Total cost** | **$0.015897** |
| **Total energy [X]** | **~4065 J** |
| Solution density [C] | 0.031718 LOC/tok |
| Correctness/$ [C] | 34 |
| Quality/J [C] | 0.000185 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0159  |  **Energy:** ~4065J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_hn0qqsuf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 726 |
| Functions | 76 |
| Classes | 13 |
| Functions/file | 5.8 |
| Classes/file | 1.0 |
| Avg lines/file | 56 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 40 |
| Decorators | 29 |
| Test files | 4 |
| Test file rate | 31% |
| Parse errors | 0 |
