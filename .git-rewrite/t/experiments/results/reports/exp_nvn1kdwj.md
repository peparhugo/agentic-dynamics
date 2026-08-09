# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r2] constraint_detection_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:23:35

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.807

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.76) with moderate resource use ($0.0115, ~2750J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.371 |
| Architecture div [H] | 0.200 |
| Structure div [H] | 0.211 |
| Thinking ratio [C] | 3.3% |
| Quality/$ [C] | 87 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 504 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.198 |
| Novelty vs baseline [H] | 0.759 |
| **Composite [H]** | **0.761** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,943 |
| Completion tokens [M] | 7,684 |
| Reasoning tokens [M] | 569 |
| Cache read tokens [M] | 119,552 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **17,196** |
| Thinking ratio [C] | 3.3% |
| Output efficiency [C] | 44.7% |
| Input cost [M] | $0.001003 |
| Output cost [M] | $0.003512 |
| Reasoning cost [M] | $0.000033 |
| Cache cost [M] | $0.006955 |
| **Total cost** | **$0.011504** |
| **Total energy [X]** | **~2750 J** |
| Solution density [C] | 0.029309 LOC/tok |
| Correctness/$ [C] | 36 |
| Quality/J [C] | 0.000277 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0115  |  **Energy:** ~2750J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_nvn1kdwj/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 504 |
| Functions | 43 |
| Classes | 21 |
| Functions/file | 3.3 |
| Classes/file | 1.6 |
| Avg lines/file | 39 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 45 |
| Decorators | 10 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
