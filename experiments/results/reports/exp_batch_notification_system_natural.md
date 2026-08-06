# Game Report: notification_system-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:notification_system:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:21:36

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.466

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=60%, quality=0.48) with moderate resource use ($0.0089, ~2536J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 17.9% |
| Quality/$ [C] | 112 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 60% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 120 |
| Cyclomatic complexity [C] | 1.0 |
| Code quality [H] | 0.983 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.482** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,572 |
| Completion tokens [M] | 2,376 |
| Reasoning tokens [M] | 2,604 |
| Cache read tokens [M] | 111,360 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **14,552** |
| Thinking ratio [C] | 17.9% |
| Output efficiency [C] | 16.3% |
| Input cost [M] | $0.001087 |
| Output cost [M] | $0.001100 |
| Reasoning cost [M] | $0.000153 |
| Cache cost [M] | $0.006560 |
| **Total cost** | **$0.008900** |
| **Total energy [X]** | **~2536 J** |
| Solution density [C] | 0.008246 LOC/tok |
| Correctness/$ [C] | 28 |
| Quality/J [C] | 0.000190 |

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
