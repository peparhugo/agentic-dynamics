# Game Report: exp_tqnuch_d-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API: JWT, rate limiting, partial spec...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:25:52

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.770

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0158, ~3757J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 2.5% |
| Quality/$ [C] | 63 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 903 |
| Cyclomatic complexity [C] | 64.0 |
| Code quality [H] | 0.111 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.747** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,187 |
| Completion tokens [M] | 10,881 |
| Reasoning tokens [M] | 595 |
| Cache read tokens [M] | 147,200 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,663** |
| Thinking ratio [C] | 2.5% |
| Output efficiency [C] | 46.0% |
| Input cost [M] | $0.001448 |
| Output cost [M] | $0.005267 |
| Reasoning cost [M] | $0.000037 |
| Cache cost [M] | $0.009068 |
| **Total cost** | **$0.015819** |
| **Total energy [X]** | **~3757 J** |
| Solution density [C] | 0.038161 LOC/tok |
| Correctness/$ [C] | 28 |
| Quality/J [C] | 0.000199 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0158  |  **Energy:** ~3757J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_tqnuch_d/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 15 |
| Total lines (Py) | 903 |
| Functions | 80 |
| Classes | 21 |
| Functions/file | 5.3 |
| Classes/file | 1.4 |
| Avg lines/file | 60 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 15 |
| Imports | 43 |
| Decorators | 39 |
| Test files | 4 |
| Test file rate | 27% |
| Parse errors | 0 |
