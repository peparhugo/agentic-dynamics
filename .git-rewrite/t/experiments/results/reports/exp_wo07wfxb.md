# Game Report: exp_wo07wfxb-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] constraint_detection_3rep...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:27:26

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.768

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0145, ~3437J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 3.7% |
| Quality/$ [C] | 69 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 750 |
| Cyclomatic complexity [C] | 55.0 |
| Code quality [H] | 0.133 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.752** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,016 |
| Completion tokens [M] | 9,876 |
| Reasoning tokens [M] | 775 |
| Cache read tokens [M] | 228,480 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,667** |
| Thinking ratio [C] | 3.7% |
| Output efficiency [C] | 47.8% |
| Input cost [M] | $0.000856 |
| Output cost [M] | $0.003438 |
| Reasoning cost [M] | $0.000034 |
| Cache cost [M] | $0.010123 |
| **Total cost** | **$0.014452** |
| **Total energy [X]** | **~3437 J** |
| Solution density [C] | 0.036290 LOC/tok |
| Correctness/$ [C] | 22 |
| Quality/J [C] | 0.000219 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0145  |  **Energy:** ~3437J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_wo07wfxb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 22 |
| Total lines (Py) | 750 |
| Functions | 83 |
| Classes | 9 |
| Functions/file | 3.8 |
| Classes/file | 0.4 |
| Avg lines/file | 34 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 10 |
| Imports | 50 |
| Decorators | 30 |
| Test files | 5 |
| Test file rate | 23% |
| Parse errors | 0 |
