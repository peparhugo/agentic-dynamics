# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r1] cd_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:41:46

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.823

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.79) with moderate resource use ($0.0106, ~2426J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.429 |
| Architecture div [H] | 0.333 |
| Structure div [H] | 0.098 |
| Thinking ratio [C] | 5.0% |
| Quality/$ [C] | 94 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 372 |
| Cyclomatic complexity [C] | 50.0 |
| Code quality [H] | 0.269 |
| Novelty vs baseline [H] | 0.889 |
| **Composite [H]** | **0.794** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,508 |
| Completion tokens [M] | 6,024 |
| Reasoning tokens [M] | 765 |
| Cache read tokens [M] | 277,248 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **15,297** |
| Thinking ratio [C] | 5.0% |
| Output efficiency [C] | 39.4% |
| Input cost [M] | $0.000510 |
| Output cost [M] | $0.001470 |
| Reasoning cost [M] | $0.000024 |
| Cache cost [M] | $0.008609 |
| **Total cost** | **$0.010612** |
| **Total energy [X]** | **~2426 J** |
| Solution density [C] | 0.024318 LOC/tok |
| Correctness/$ [C] | 21 |
| Quality/J [C] | 0.000327 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0106  |  **Energy:** ~2426J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_uaqvwo_n/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 20 |
| Total lines (Py) | 372 |
| Functions | 41 |
| Classes | 5 |
| Functions/file | 2.0 |
| Classes/file | 0.2 |
| Avg lines/file | 19 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 12 |
| Imports | 43 |
| Decorators | 47 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
