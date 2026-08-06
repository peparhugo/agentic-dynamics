# Game Report: exp_9o_y1a_8-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT and SQLite...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:16:36

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.769

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.0214, ~4873J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 2.9% |
| Quality/$ [C] | 47 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 1030 |
| Cyclomatic complexity [C] | 92.0 |
| Code quality [H] | 0.097 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.702** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16,099 |
| Completion tokens [M] | 13,753 |
| Reasoning tokens [M] | 897 |
| Cache read tokens [M] | 463,488 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **30,749** |
| Thinking ratio [C] | 2.9% |
| Output efficiency [C] | 44.7% |
| Input cost [M] | $0.001102 |
| Output cost [M] | $0.003837 |
| Reasoning cost [M] | $0.000032 |
| Cache cost [M] | $0.016457 |
| **Total cost** | **$0.021429** |
| **Total energy [X]** | **~4873 J** |
| Solution density [C] | 0.033497 LOC/tok |
| Correctness/$ [C] | 12 |
| Quality/J [C] | 0.000144 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0214  |  **Energy:** ~4873J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_9o_y1a_8/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 17 |
| Total lines (Py) | 1030 |
| Functions | 95 |
| Classes | 22 |
| Functions/file | 5.6 |
| Classes/file | 1.3 |
| Avg lines/file | 61 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 12 |
| Imports | 49 |
| Decorators | 40 |
| Test files | 5 |
| Test file rate | 29% |
| Parse errors | 0 |
