# Game Report: notification_system-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:notification_system:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:49:52

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.466

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=60%, quality=0.52) with moderate resource use ($0.0089, ~2536J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 17.9% |
| Quality/$ | 180 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 60% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 120 |
| Cyclomatic complexity | 1.0 |
| Code quality | 0.983 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.525** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,572 |
| Completion tokens | 2,376 |
| Reasoning tokens | 2,604 |
| **Total tokens** | **14,552** |
| Thinking ratio | 17.9% |
| Output efficiency | 16.3% |
| Input cost | $0.002584 |
| Output cost | $0.002614 |
| Reasoning cost | $0.000365 |
| **Total cost** | **$0.008900** |
| **Total energy** | **~2536 J** |
| Solution density | 0.008246 LOC/tok |
| Correctness/$ | 108 |
| Quality/J | 0.000207 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 60%  |  **Cost:** $0.0089  |  **Energy:** ~2536J  |  **Thinking:** 18%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_notification_system_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 3 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 117 |
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
