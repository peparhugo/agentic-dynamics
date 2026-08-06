# Game Report: exp_nlme9vjk-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:05

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.681

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.48) with moderate resource use ($0.0126, ~3342J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 12.0% |
| Quality/$ | 79 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 472 |
| Cyclomatic complexity | 81.0 |
| Code quality | 0.212 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.483** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,206 |
| Completion tokens | 6,865 |
| Reasoning tokens | 2,184 |
| **Total tokens** | **18,255** |
| Thinking ratio | 12.0% |
| Output efficiency | 37.6% |
| **Total cost** | **$0.012634** |
| **Total energy** | **~3342 J** |
| Solution density | 0.025856 LOC/tok |
| Correctness/$ | 77 |
| Quality/J | 0.000145 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0126  |  **Energy:** ~3342J  |  **Thinking:** 12%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_nlme9vjk/session.jsonl)
- [Generated code](./exp_nlme9vjk/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 458 |
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
