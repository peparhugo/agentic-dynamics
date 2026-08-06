# Game Report: data_table-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:data_table:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:47:30

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.477

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=60%, quality=0.38) with moderate resource use ($0.0194, ~4849J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 4.0% |
| Quality/$ | 50 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 60% (0/0 tests) |
| Constraint satisfaction | 25% (1/4 constraints) |
| Lines of code | 839 |
| Cyclomatic complexity | 122.0 |
| Code quality | 0.119 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.384** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,028 |
| Completion tokens | 16,237 |
| Reasoning tokens | 1,005 |
| **Total tokens** | **25,270** |
| Thinking ratio | 4.0% |
| Output efficiency | 64.3% |
| Input cost | $0.002168 |
| Output cost | $0.017861 |
| Reasoning cost | $0.000141 |
| **Total cost** | **$0.019413** |
| **Total energy** | **~4849 J** |
| Solution density | 0.033201 LOC/tok |
| Correctness/$ | 30 |
| Quality/J | 0.000079 |

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
