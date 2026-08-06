# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r1] constraint_detection_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:31:11

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.789

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.77) with moderate resource use ($0.0154, ~3774J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.309 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.060 |
| Thinking ratio [C] | 3.4% |
| Quality/$ [C] | 65 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 770 |
| Cyclomatic complexity [C] | 79.0 |
| Code quality [H] | 0.130 |
| Novelty vs baseline [H] | 0.638 |
| **Composite [H]** | **0.772** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,166 |
| Completion tokens [M] | 11,728 |
| Reasoning tokens [M] | 730 |
| Cache read tokens [M] | 152,704 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **21,624** |
| Thinking ratio [C] | 3.4% |
| Output efficiency [C] | 54.2% |
| Input cost [M] | $0.001033 |
| Output cost [M] | $0.005383 |
| Reasoning cost [M] | $0.000043 |
| Cache cost [M] | $0.008921 |
| **Total cost** | **$0.015379** |
| **Total energy [X]** | **~3774 J** |
| Solution density [C] | 0.035609 LOC/tok |
| Correctness/$ [C] | 27 |
| Quality/J [C] | 0.000204 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0154  |  **Energy:** ~3774J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_quas142w/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 26 |
| Total lines (Py) | 770 |
| Functions | 79 |
| Classes | 13 |
| Functions/file | 3.0 |
| Classes/file | 0.5 |
| Avg lines/file | 30 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 16 |
| Imports | 65 |
| Decorators | 57 |
| Test files | 6 |
| Test file rate | 23% |
| Parse errors | 0 |
