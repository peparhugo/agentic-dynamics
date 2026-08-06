# Game Report: exp_f1cezegh-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:07

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.769

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.53) with moderate resource use ($0.0167, ~3949J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 2.8% |
| Quality/$ | 60 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 1178 |
| Cyclomatic complexity | 73.0 |
| Code quality | 0.085 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.528** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,312 |
| Completion tokens | 12,636 |
| Reasoning tokens | 634 |
| **Total tokens** | **22,582** |
| Thinking ratio | 2.8% |
| Output efficiency | 56.0% |
| **Total cost** | **$0.016716** |
| **Total energy** | **~3949 J** |
| Solution density | 0.052165 LOC/tok |
| Correctness/$ | 61 |
| Quality/J | 0.000134 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0167  |  **Energy:** ~3949J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_f1cezegh/session.jsonl)
- [Generated code](./exp_f1cezegh/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 16 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1164 |
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
