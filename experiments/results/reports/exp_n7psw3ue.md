# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:37:15

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.711

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0206, ~7178J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 31.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 694 |
| Cyclomatic complexity [C] | 53.0 |
| Code quality [H] | 0.144 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.711** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 15,343 |
| Completion tokens [M] | 5,702 |
| Reasoning tokens [M] | 9,871 |
| Cache read tokens [M] | 99,584 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **30,916** |
| Thinking ratio [C] | 31.9% |
| Output efficiency [C] | 18.4% |
| Input cost [M] | $0.003313 |
| Output cost [M] | $0.005016 |
| Reasoning cost [M] | $0.001105 |
| Cache cost [M] | $0.011150 |
| **Total cost** | **$0.020584** |
| **Total energy [X]** | **~7178 J** |
| Solution density [C] | 0.022448 LOC/tok |
| Correctness/$ [C] | 39 |
| Quality/J [C] | 0.000099 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0206  |  **Energy:** ~7178J  |  **Thinking:** 32%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_n7psw3ue/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 16 |
| Total lines (Py) | 694 |
| Functions | 57 |
| Classes | 18 |
| Functions/file | 3.6 |
| Classes/file | 1.1 |
| Avg lines/file | 43 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 11 |
| Imports | 48 |
| Decorators | 24 |
| Test files | 2 |
| Test file rate | 12% |
| Parse errors | 0 |
