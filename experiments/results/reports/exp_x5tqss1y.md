# Game Report: exp_x5tqss1y-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:55:08

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.697

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.46) with moderate resource use ($0.0185, ~4258J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 4.2% |
| Quality/$ | 54 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 883 |
| Cyclomatic complexity | 65.0 |
| Code quality | 0.113 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.463** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,217 |
| Completion tokens | 12,869 |
| Reasoning tokens | 1,022 |
| **Total tokens** | **24,108** |
| Thinking ratio | 4.2% |
| Output efficiency | 53.4% |
| **Total cost** | **$0.018550** |
| **Total energy** | **~4258 J** |
| Solution density | 0.036627 LOC/tok |
| Correctness/$ | 47 |
| Quality/J | 0.000109 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0185  |  **Energy:** ~4258J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_x5tqss1y/session.jsonl)
- [Generated code](./exp_x5tqss1y/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 25 |
| JS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1463 |
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
