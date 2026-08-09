# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r2] cd_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:42:54

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.796

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.77) with moderate resource use ($0.0156, ~3904J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.348 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.148 |
| Thinking ratio [C] | 3.2% |
| Quality/$ [C] | 64 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 962 |
| Cyclomatic complexity [C] | 92.0 |
| Code quality [H] | 0.104 |
| Novelty vs baseline [H] | 0.680 |
| **Composite [H]** | **0.773** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,502 |
| Completion tokens [M] | 12,612 |
| Reasoning tokens [M] | 688 |
| Cache read tokens [M] | 98,560 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **21,802** |
| Thinking ratio [C] | 3.2% |
| Output efficiency [C] | 57.8% |
| Input cost [M] | $0.001193 |
| Output cost [M] | $0.007211 |
| Reasoning cost [M] | $0.000050 |
| Cache cost [M] | $0.007172 |
| **Total cost** | **$0.015627** |
| **Total energy [X]** | **~3904 J** |
| Solution density [C] | 0.044124 LOC/tok |
| Correctness/$ [C] | 33 |
| Quality/J [C] | 0.000198 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0156  |  **Energy:** ~3904J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_w8ayd_ci/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 27 |
| Total lines (Py) | 962 |
| Functions | 101 |
| Classes | 14 |
| Functions/file | 3.7 |
| Classes/file | 0.5 |
| Avg lines/file | 36 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 12 |
| Imports | 70 |
| Decorators | 75 |
| Test files | 4 |
| Test file rate | 15% |
| Parse errors | 0 |
