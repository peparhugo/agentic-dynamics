# Game Report: data_table-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:data_table:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:16:37

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.477

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=60%, quality=0.38) with moderate resource use ($0.0194, ~4849J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 4.0% |
| Quality/$ [C] | 52 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 60% (0/0 tests) [H] |
| Constraint satisfaction [H] | 25% (1/4 constraints) |
| Lines of code [M] | 839 |
| Cyclomatic complexity [C] | 122.0 |
| Code quality [H] | 0.119 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.384** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,028 |
| Completion tokens [M] | 16,237 |
| Reasoning tokens [M] | 1,005 |
| Cache read tokens [M] | 253,824 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **25,270** |
| Thinking ratio [C] | 4.0% |
| Output efficiency [C] | 64.3% |
| Input cost [M] | $0.000755 |
| Output cost [M] | $0.006224 |
| Reasoning cost [M] | $0.000049 |
| Cache cost [M] | $0.012384 |
| **Total cost** | **$0.019413** |
| **Total energy [X]** | **~4849 J** |
| Solution density [C] | 0.033201 LOC/tok |
| Correctness/$ [C] | 11 |
| Quality/J [C] | 0.000079 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 60%  |  **Cost:** $0.0194  |  **Energy:** ~4849J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_data_table_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 13 |
| TSX files | 1 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1377 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
