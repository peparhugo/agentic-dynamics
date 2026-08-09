# Game Report: exp_hcnattl6-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT auth and pytest...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:21:09

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.765

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.0210, ~5219J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 5.1% |
| Quality/$ [C] | 48 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 1070 |
| Cyclomatic complexity [C] | 141.0 |
| Code quality [H] | 0.093 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.701** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,519 |
| Completion tokens [M] | 15,260 |
| Reasoning tokens [M] | 1,506 |
| Cache read tokens [M] | 257,152 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **29,285** |
| Thinking ratio [C] | 5.1% |
| Output efficiency [C] | 52.1% |
| Input cost [M] | $0.001257 |
| Output cost [M] | $0.006242 |
| Reasoning cost [M] | $0.000078 |
| Cache cost [M] | $0.013387 |
| **Total cost** | **$0.020964** |
| **Total energy [X]** | **~5219 J** |
| Solution density [C] | 0.036537 LOC/tok |
| Correctness/$ [C] | 18 |
| Quality/J [C] | 0.000134 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0210  |  **Energy:** ~5219J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_hcnattl6/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 19 |
| Total lines (Py) | 1070 |
| Functions | 109 |
| Classes | 14 |
| Functions/file | 5.7 |
| Classes/file | 0.7 |
| Avg lines/file | 56 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 33 |
| Decorators | 32 |
| Test files | 4 |
| Test file rate | 21% |
| Parse errors | 0 |
