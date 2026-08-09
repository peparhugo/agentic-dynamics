# Game Report: twitter_timeline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:twitter_timeline:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:18:42

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.51) with moderate resource use ($0.0095, ~2418J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.6% |
| Quality/$ [C] | 105 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 439 |
| Cyclomatic complexity [C] | 42.0 |
| Code quality [H] | 0.228 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.513** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,434 |
| Completion tokens [M] | 5,276 |
| Reasoning tokens [M] | 1,128 |
| Cache read tokens [M] | 75,904 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **14,838** |
| Thinking ratio [C] | 7.6% |
| Output efficiency [C] | 35.6% |
| Input cost [M] | $0.001149 |
| Output cost [M] | $0.002927 |
| Reasoning cost [M] | $0.000080 |
| Cache cost [M] | $0.005360 |
| **Total cost** | **$0.009515** |
| **Total energy [X]** | **~2418 J** |
| Solution density [C] | 0.029586 LOC/tok |
| Correctness/$ [C] | 53 |
| Quality/J [C] | 0.000212 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0095  |  **Energy:** ~2418J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_twitter_timeline_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 11 |
| Total lines (Py) | 439 |
| Functions | 77 |
| Classes | 16 |
| Functions/file | 7.0 |
| Classes/file | 1.5 |
| Avg lines/file | 40 |
| Type hints | 86% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 44 |
| Decorators | 1 |
| Test files | 1 |
| Test file rate | 9% |
| Parse errors | 0 |
