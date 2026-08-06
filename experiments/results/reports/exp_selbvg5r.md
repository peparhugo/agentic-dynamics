# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5.5  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_gather_gpt_5_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:31:56

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.839

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.71) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.3159, ~2859J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.715 |
| Architecture div [H] | 0.750 |
| Structure div [H] | 0.417 |
| Thinking ratio [C] | 2.9% |
| Quality/$ [C] | 3 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (9/9 tests) [M] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 288 |
| Cyclomatic complexity [C] | 47.0 |
| Code quality [H] | 0.347 |
| Novelty vs baseline [H] | 0.966 |
| **Composite [H]** | **0.822** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16,911 |
| Completion tokens [M] | 5,216 |
| Reasoning tokens [M] | 652 |
| Cache read tokens [M] | 110,592 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,779** |
| Thinking ratio [C] | 2.9% |
| Output efficiency [C] | 22.9% |
| Input cost [M] | $0.044834 |
| Output cost [M] | $0.110629 |
| Reasoning cost [M] | $0.013829 |
| Cache cost [M] | $0.146600 |
| **Total cost** | **$0.315891** |
| **Total energy [X]** | **~2859 J** |
| Solution density [C] | 0.012643 LOC/tok |
| Correctness/$ [C] | 7 |
| Quality/J [C] | 0.000287 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.3159  |  **Energy:** ~2859J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_selbvg5r/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 288 |
| Functions | 35 |
| Classes | 1 |
| Functions/file | 11.7 |
| Classes/file | 0.3 |
| Avg lines/file | 96 |
| Type hints | 34% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 11 |
| Decorators | 17 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 9 |
| Failed | 0 |
| Errors | 0 |
| Total | 9 |
| Pass rate | 100% |
| Duration | 0.8s |
