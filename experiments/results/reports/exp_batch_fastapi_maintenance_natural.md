# Game Report: fastapi_maintenance-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:fastapi_maintenance:baseline] ds_natural...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:45

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.923

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0026, ~494J, 1% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 0.8% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

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
| Prompt tokens [M] | 5,657 |
| Completion tokens [M] | 87 |
| Reasoning tokens [M] | 45 |
| Cache read tokens [M] | 1,920 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **5,789** |
| Thinking ratio [C] | 0.8% |
| Output efficiency [C] | 1.5% |
| Input cost [M] | $0.002388 |
| Output cost [M] | $0.000110 |
| Reasoning cost [M] | $0.000057 |
| Cache cost [M] | $0.000027 |
| **Total cost** | **$0.002583** |
| **Total energy [X]** | **~494 J** |
| Solution density [C] | 0.521852 LOC/tok |
| Correctness/$ [C] | 248 |
| Quality/J [C] | 0.001221 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0026  |  **Energy:** ~494J  |  **Thinking:** 1%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_fastapi_maintenance_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1138 |
| JS files | 4 |
| Total lines (Py) | 96395 |
| Total lines (TS/TSX) | 526 |
| Functions | 3991 |
| Classes | 692 |
| Functions/file | 3.5 |
| Classes/file | 0.6 |
| Avg lines/file | 85 |
| Type hints | 42% |
| Docstrings | 3% |
| Error handlers | 98 |
| Imports | 3553 |
| Decorators | 1457 |
| Test files | 512 |
| Test file rate | 45% |
| Parse errors | 0 |
