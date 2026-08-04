# Game Report: exp_tqnuch_d-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API: JWT, rate limiting, partial spec...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:57:34

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.770

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.66) with moderate resource use ($0.0158, ~3757J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 2.5% |
| Quality/$ | 65 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 903 |
| Cyclomatic complexity | 64.0 |
| Code quality | 0.111 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.661** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12,187 |
| Completion tokens | 10,881 |
| Reasoning tokens | 595 |
| **Total tokens** | **23,663** |
| Thinking ratio | 2.5% |
| Output efficiency | 46.0% |
| Input cost | $0.003290 |
| Output cost | $0.011969 |
| Reasoning cost | $0.000083 |
| **Total cost** | **$0.015819** |
| **Total energy** | **~3757 J** |
| Solution density | 0.038161 LOC/tok |
| Correctness/$ | 65 |
| Quality/J | 0.000176 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0158  |  **Energy:** ~3757J  |  **Thinking:** 3%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 15 |
| Total lines | 903 |
| Functions | 80 |
| Classes | 21 |
| Functions/file | 5.3 |
| Classes/file | 1.4 |
| Avg lines/file | 60 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 15 |
| Imports | 43 |
| Decorators | 39 |
| Test files | 4 |
| Test file rate | 27% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_tqnuch_d/code/)
