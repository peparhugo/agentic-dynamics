# Game Report: exp_1erxln69-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT and SQLite...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:39:26

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.57) with moderate resource use ($0.0214, ~5245J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 4.1% |
| Quality/$ | 46 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 1266 |
| Cyclomatic complexity | 180.0 |
| Code quality | 0.079 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.569** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,187 |
| Completion tokens | 17,302 |
| Reasoning tokens | 1,129 |
| **Total tokens** | **27,618** |
| Thinking ratio | 4.1% |
| Output efficiency | 62.6% |
| Input cost | $0.002480 |
| Output cost | $0.019032 |
| Reasoning cost | $0.000158 |
| **Total cost** | **$0.021444** |
| **Total energy** | **~5245 J** |
| Solution density | 0.045840 LOC/tok |
| Correctness/$ | 46 |
| Quality/J | 0.000109 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0214  |  **Energy:** ~5245J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_1erxln69/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 18 |
| Total lines (Py) | 1266 |
| Functions | 126 |
| Classes | 5 |
| Functions/file | 7.0 |
| Classes/file | 0.3 |
| Avg lines/file | 70 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 50 |
| Decorators | 38 |
| Test files | 5 |
| Test file rate | 28% |
| Parse errors | 0 |
