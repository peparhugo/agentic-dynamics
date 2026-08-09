# Game Report: exp_m3c9h6l0-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] constraint_detection_3rep...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:36:24

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.768

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0169, ~4110J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 3.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 891 |
| Cyclomatic complexity [C] | 74.0 |
| Code quality [H] | 0.112 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.747** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,139 |
| Completion tokens [M] | 12,622 |
| Reasoning tokens [M] | 843 |
| Cache read tokens [M] | 211,712 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,604** |
| Thinking ratio [C] | 3.6% |
| Output efficiency [C] | 53.5% |
| Input cost [M] | $0.000997 |
| Output cost [M] | $0.005057 |
| Reasoning cost [M] | $0.000043 |
| Cache cost [M] | $0.010795 |
| **Total cost** | **$0.016892** |
| **Total energy [X]** | **~4110 J** |
| Solution density [C] | 0.037748 LOC/tok |
| Correctness/$ [C] | 22 |
| Quality/J [C] | 0.000182 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0169  |  **Energy:** ~4110J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_m3c9h6l0/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 28 |
| Total lines (Py) | 891 |
| Functions | 86 |
| Classes | 22 |
| Functions/file | 3.1 |
| Classes/file | 0.8 |
| Avg lines/file | 32 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 63 |
| Decorators | 59 |
| Test files | 6 |
| Test file rate | 21% |
| Parse errors | 0 |
