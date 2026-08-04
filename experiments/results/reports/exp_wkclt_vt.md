# Game Report: exp_wkclt_vt-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Building Flask task management API + flaw analysis...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:58:51

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.758

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.58) with moderate resource use ($0.0157, ~4138J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 8.5% |
| Quality/$ | 67 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 853 |
| Cyclomatic complexity | 92.0 |
| Code quality | 0.117 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.577** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,926 |
| Completion tokens | 11,099 |
| Reasoning tokens | 1,853 |
| **Total tokens** | **21,878** |
| Thinking ratio | 8.5% |
| Output efficiency | 50.7% |
| Input cost | $0.002410 |
| Output cost | $0.012209 |
| Reasoning cost | $0.000259 |
| **Total cost** | **$0.015723** |
| **Total energy** | **~4138 J** |
| Solution density | 0.038989 LOC/tok |
| Correctness/$ | 67 |
| Quality/J | 0.000139 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0157  |  **Energy:** ~4138J  |  **Thinking:** 8%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines | 853 |
| Functions | 77 |
| Classes | 13 |
| Functions/file | 7.7 |
| Classes/file | 1.3 |
| Avg lines/file | 85 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 26 |
| Decorators | 22 |
| Test files | 3 |
| Test file rate | 30% |
| Parse errors | 0 |
