# Game Report: fastapi_maintenance-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:fastapi_maintenance:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:18:26

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.60) with moderate resource use ($0.0303, ~6524J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 8.0% |
| Quality/$ [C] | 33 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 3021 |
| Cyclomatic complexity [C] | 153.0 |
| Code quality [H] | 0.033 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.603** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 43,352 |
| Completion tokens [M] | 4,756 |
| Reasoning tokens [M] | 4,174 |
| Cache read tokens [M] | 1,013,888 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **52,282** |
| Thinking ratio [C] | 8.0% |
| Output efficiency [C] | 9.1% |
| Input cost [M] | $0.002224 |
| Output cost [M] | $0.000994 |
| Reasoning cost [M] | $0.000111 |
| Cache cost [M] | $0.026973 |
| **Total cost** | **$0.030303** |
| **Total energy [X]** | **~6524 J** |
| Solution density [C] | 0.057783 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000092 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0303  |  **Energy:** ~6524J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_fastapi_maintenance_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1136 |
| JS files | 4 |
| Total lines (Py) | 96299 |
| Total lines (TS/TSX) | 528 |
| Functions | 3986 |
| Classes | 692 |
| Functions/file | 3.5 |
| Classes/file | 0.6 |
| Avg lines/file | 85 |
| Type hints | 42% |
| Docstrings | 3% |
| Error handlers | 98 |
| Imports | 3548 |
| Decorators | 1456 |
| Test files | 511 |
| Test file rate | 45% |
| Parse errors | 0 |
