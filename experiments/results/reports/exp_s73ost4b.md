# Game Report: exp_s73ost4b-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API with JWT, pagination, rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:04:27

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.770

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0167, ~3890J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 2.5% |
| Quality/$ | 61 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 100% (7/7 constraints) |
| Lines of code | 899 |
| Cyclomatic complexity | 83.0 |
| Code quality | 0.111 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.747** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,342 |
| Completion tokens | 12,536 |
| Reasoning tokens | 552 |
| **Total tokens** | **22,430** |
| Thinking ratio | 2.5% |
| Output efficiency | 55.9% |
| Input cost | $0.002522 |
| Output cost | $0.013790 |
| Reasoning cost | $0.000077 |
| **Total cost** | **$0.016746** |
| **Total energy** | **~3890 J** |
| Solution density | 0.040080 LOC/tok |
| Correctness/$ | 61 |
| Quality/J | 0.000192 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0167  |  **Energy:** ~3890J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_s73ost4b/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 21 |
| Total lines (Py) | 899 |
| Functions | 105 |
| Classes | 18 |
| Functions/file | 5.0 |
| Classes/file | 0.9 |
| Avg lines/file | 43 |
| Type hints | 3% |
| Docstrings | 0% |
| Error handlers | 13 |
| Imports | 66 |
| Decorators | 72 |
| Test files | 8 |
| Test file rate | 38% |
| Parse errors | 0 |
