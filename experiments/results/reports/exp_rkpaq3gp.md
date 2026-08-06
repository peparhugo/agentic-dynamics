# Game Report: remove_critical_constraint_s0.5_r2-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [remove_critical_constraint_s0.5_r2] constraint_detection_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:31:31

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.779

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.72) with moderate resource use ($0.0159, ~3925J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.294 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.078 |
| Thinking ratio [C] | 3.3% |
| Quality/$ [C] | 63 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 782 |
| Cyclomatic complexity [C] | 63.0 |
| Code quality [H] | 0.128 |
| Novelty vs baseline [H] | 0.569 |
| **Composite [H]** | **0.718** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,123 |
| Completion tokens [M] | 12,406 |
| Reasoning tokens [M] | 727 |
| Cache read tokens [M] | 144,512 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,256** |
| Thinking ratio [C] | 3.3% |
| Output efficiency [C] | 55.7% |
| Input cost [M] | $0.001076 |
| Output cost [M] | $0.005961 |
| Reasoning cost [M] | $0.000044 |
| Cache cost [M] | $0.008837 |
| **Total cost** | **$0.015918** |
| **Total energy [X]** | **~3925 J** |
| Solution density [C] | 0.035137 LOC/tok |
| Correctness/$ [C] | 27 |
| Quality/J [C] | 0.000183 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0159  |  **Energy:** ~3925J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_rkpaq3gp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 25 |
| Total lines (Py) | 782 |
| Functions | 77 |
| Classes | 19 |
| Functions/file | 3.1 |
| Classes/file | 0.8 |
| Avg lines/file | 31 |
| Type hints | 13% |
| Docstrings | 0% |
| Error handlers | 18 |
| Imports | 64 |
| Decorators | 43 |
| Test files | 5 |
| Test file rate | 20% |
| Parse errors | 0 |
