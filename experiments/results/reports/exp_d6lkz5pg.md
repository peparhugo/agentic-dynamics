# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Building URL shortener with REST API and analytics...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:50:55

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.691

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.67) with moderate resource use ($0.0126, ~3009J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.2% |
| Quality/$ | 96 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 67% (4/6 constraints) |
| Lines of code | 227 |
| Cyclomatic complexity | 21.0 |
| Code quality | 0.591 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.673** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,186 |
| Completion tokens | 6,842 |
| Reasoning tokens | 1,320 |
| **Total tokens** | **18,348** |
| Thinking ratio | 7.2% |
| Output efficiency | 37.3% |
| Input cost | $0.002750 |
| Output cost | $0.007526 |
| Reasoning cost | $0.000185 |
| **Total cost** | **$0.012649** |
| **Total energy** | **~3009 J** |
| Solution density | 0.012372 LOC/tok |
| Correctness/$ | 76 |
| Quality/J | 0.000224 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0126  |  **Energy:** ~3009J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_d6lkz5pg/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 4 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 223 |
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
