# Game Report: web_crawler-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:web_crawler:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:51:13

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.732

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.53) with moderate resource use ($0.0116, ~3571J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 21.3% |
| Quality/$ | 129 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 320 |
| Cyclomatic complexity | 83.0 |
| Code quality | 0.312 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.530** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,264 |
| Completion tokens | 4,029 |
| Reasoning tokens | 3,879 |
| **Total tokens** | **18,172** |
| Thinking ratio | 21.3% |
| Output efficiency | 22.2% |
| Input cost | $0.002771 |
| Output cost | $0.004432 |
| Reasoning cost | $0.000543 |
| **Total cost** | **$0.011600** |
| **Total energy** | **~3571 J** |
| Solution density | 0.017610 LOC/tok |
| Correctness/$ | 129 |
| Quality/J | 0.000149 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0116  |  **Energy:** ~3571J  |  **Thinking:** 21%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines | 320 |
| Functions | 33 |
| Classes | 8 |
| Functions/file | 8.2 |
| Classes/file | 2.0 |
| Avg lines/file | 80 |
| Type hints | 73% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 30 |
| Decorators | 2 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
