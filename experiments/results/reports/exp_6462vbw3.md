# Game Report: exp_6462vbw3-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API with JWT, pagination, rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:47:00

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.770

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.58) with moderate resource use ($0.0170, ~4012J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 2.6% |
| Quality/$ | 61 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 748 |
| Cyclomatic complexity | 72.0 |
| Code quality | 0.134 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.580** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12,058 |
| Completion tokens | 11,954 |
| Reasoning tokens | 634 |
| **Total tokens** | **24,646** |
| Thinking ratio | 2.6% |
| Output efficiency | 48.5% |
| Input cost | $0.003256 |
| Output cost | $0.013149 |
| Reasoning cost | $0.000089 |
| **Total cost** | **$0.016988** |
| **Total energy** | **~4012 J** |
| Solution density | 0.030350 LOC/tok |
| Correctness/$ | 61 |
| Quality/J | 0.000145 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0170  |  **Energy:** ~4012J  |  **Thinking:** 3%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 30 |
| Total lines | 748 |
| Functions | 94 |
| Classes | 11 |
| Functions/file | 3.1 |
| Classes/file | 0.4 |
| Avg lines/file | 25 |
| Type hints | 14% |
| Docstrings | 4% |
| Error handlers | 12 |
| Imports | 77 |
| Decorators | 51 |
| Test files | 5 |
| Test file rate | 17% |
| Parse errors | 0 |
