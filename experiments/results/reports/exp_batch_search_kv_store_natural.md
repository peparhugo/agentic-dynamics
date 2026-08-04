# Game Report: search_kv_store-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:search_kv_store:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:51:12

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.53) with moderate resource use ($0.0177, ~4658J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.8% |
| Quality/$ | 57 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 1239 |
| Cyclomatic complexity | 357.0 |
| Code quality | 0.081 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.527** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 7,557 |
| Completion tokens | 13,892 |
| Reasoning tokens | 1,826 |
| **Total tokens** | **23,275** |
| Thinking ratio | 7.8% |
| Output efficiency | 59.7% |
| Input cost | $0.002040 |
| Output cost | $0.015281 |
| Reasoning cost | $0.000256 |
| **Total cost** | **$0.017714** |
| **Total energy** | **~4658 J** |
| Solution density | 0.053233 LOC/tok |
| Correctness/$ | 57 |
| Quality/J | 0.000113 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0177  |  **Energy:** ~4658J  |  **Thinking:** 8%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines | 1239 |
| Functions | 60 |
| Classes | 7 |
| Functions/file | 7.5 |
| Classes/file | 0.9 |
| Avg lines/file | 155 |
| Type hints | 3% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 13 |
| Decorators | 0 |
| Test files | 1 |
| Test file rate | 12% |
| Parse errors | 5 |
