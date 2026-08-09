# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_final_gpt_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:36:06

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.834

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0634, ~2031J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.729 |
| Architecture div [H] | 0.800 |
| Structure div [H] | 0.393 |
| Thinking ratio [C] | 5.6% |
| Quality/$ [C] | 16 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 203 |
| Cyclomatic complexity [C] | 43.0 |
| Code quality [H] | 0.493 |
| Novelty vs baseline [H] | 0.970 |
| **Composite [H]** | **0.851** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,457 |
| Completion tokens [M] | 3,494 |
| Reasoning tokens [M] | 832 |
| Cache read tokens [M] | 56,832 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **14,783** |
| Thinking ratio [C] | 5.6% |
| Output efficiency [C] | 23.6% |
| Input cost [M] | $0.009027 |
| Output cost [M] | $0.024131 |
| Reasoning cost [M] | $0.005746 |
| Cache cost [M] | $0.024531 |
| **Total cost** | **$0.063435** |
| **Total energy [X]** | **~2031 J** |
| Solution density [C] | 0.013732 LOC/tok |
| Correctness/$ [C] | 11 |
| Quality/J [C] | 0.000419 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0634  |  **Energy:** ~2031J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_lw9zhue9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 203 |
| Functions | 27 |
| Classes | 1 |
| Functions/file | 4.5 |
| Classes/file | 0.2 |
| Avg lines/file | 34 |
| Type hints | 43% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 20 |
| Decorators | 9 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
