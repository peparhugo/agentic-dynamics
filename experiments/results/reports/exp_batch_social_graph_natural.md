# Game Report: social_graph-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:social_graph:baseline] ds_natural...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:25

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.899

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0119, ~3111J, 9% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 8.8% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 676 |
| Cyclomatic complexity [C] | 188.0 |
| Code quality [H] | 0.148 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.497** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6,752 |
| Completion tokens [M] | 8,233 |
| Reasoning tokens [M] | 1,442 |
| Cache read tokens [M] | 145,920 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **16,427** |
| Thinking ratio [C] | 8.8% |
| Output efficiency [C] | 50.1% |
| Input cost [M] | $0.001974 |
| Output cost [M] | $0.007222 |
| Reasoning cost [M] | $0.001265 |
| Cache cost [M] | $0.001422 |
| **Total cost** | **$0.011883** |
| **Total energy [X]** | **~3111 J** |
| Solution density [C] | 0.041152 LOC/tok |
| Correctness/$ [C] | 37 |
| Quality/J [C] | 0.000160 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0119  |  **Energy:** ~3111J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_social_graph_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines (Py) | 676 |
| Functions | 92 |
| Classes | 13 |
| Functions/file | 10.2 |
| Classes/file | 1.4 |
| Avg lines/file | 75 |
| Type hints | 107% |
| Docstrings | 8% |
| Error handlers | 0 |
| Imports | 45 |
| Decorators | 6 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
