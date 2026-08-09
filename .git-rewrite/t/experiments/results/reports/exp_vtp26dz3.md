# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_gather_gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:26:13

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.819

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.55) and found a novel correct solution (novelty=0.85, correctness=100%). Cost: $0.5667, ~1324J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.551 |
| Architecture div [H] | 0.600 |
| Structure div [H] | 0.186 |
| Thinking ratio [C] | 4.3% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0008 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 291 |
| Cyclomatic complexity [C] | 59.0 |
| Code quality [H] | 0.344 |
| Novelty vs baseline [H] | 0.851 |
| **Composite [H]** | **0.846** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 30 |
| Completion tokens [M] | 5,262 |
| Reasoning tokens [M] | 237 |
| Cache read tokens [M] | 78,722 |
| Cache write tokens [M] | 12,623 |
| **Total tokens** | **5,529** |
| Thinking ratio [C] | 4.3% |
| Output efficiency [C] | 95.2% |
| Input cost [M] | $0.000157 |
| Output cost [M] | $0.219627 |
| Reasoning cost [M] | $0.009892 |
| Cache cost [M] | $0.337074 |
| **Total cost** | **$0.566750** |
| **Total energy [X]** | **~1324 J** |
| Solution density [C] | 0.052632 LOC/tok |
| Correctness/$ [C] | 7 |
| Quality/J [C] | 0.000639 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.5667  |  **Energy:** ~1324J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_vtp26dz3/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 291 |
| Functions | 36 |
| Classes | 1 |
| Functions/file | 12.0 |
| Classes/file | 0.3 |
| Avg lines/file | 97 |
| Type hints | 38% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 17 |
| Decorators | 20 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |
