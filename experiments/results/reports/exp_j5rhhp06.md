# Game Report: standardized_test-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [standardized_test] deepseek...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:26:36

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.804

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.68) with moderate resource use ($0.0091, ~2196J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.276 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.250 |
| Thinking ratio [C] | 4.6% |
| Quality/$ [C] | 110 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 369 |
| Cyclomatic complexity [C] | 41.0 |
| Code quality [H] | 0.271 |
| Novelty vs baseline [H] | 0.669 |
| **Composite [H]** | **0.676** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,225 |
| Completion tokens [M] | 5,339 |
| Reasoning tokens [M] | 660 |
| Cache read tokens [M] | 91,392 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **14,224** |
| Thinking ratio [C] | 4.6% |
| Output efficiency [C] | 37.5% |
| Input cost [M] | $0.000966 |
| Output cost [M] | $0.002555 |
| Reasoning cost [M] | $0.000040 |
| Cache cost [M] | $0.005567 |
| **Total cost** | **$0.009128** |
| **Total energy [X]** | **~2196 J** |
| Solution density [C] | 0.025942 LOC/tok |
| Correctness/$ [C] | 48 |
| Quality/J [C] | 0.000308 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0091  |  **Energy:** ~2196J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_j5rhhp06/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 369 |
| Functions | 49 |
| Classes | 9 |
| Functions/file | 7.0 |
| Classes/file | 1.3 |
| Avg lines/file | 53 |
| Type hints | 35% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 27 |
| Decorators | 7 |
| Test files | 1 |
| Test file rate | 14% |
| Parse errors | 0 |
