# Game Report: perturbed-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:perturbed:forced] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:32:19

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0323, ~5369J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 5.4% |
| Quality/$ [C] | 31 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (3/3 tests) [M] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 281 |
| Cyclomatic complexity [C] | 52.0 |
| Code quality [H] | 0.356 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.753** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 36,992 |
| Completion tokens [M] | 5,507 |
| Reasoning tokens [M] | 2,432 |
| Cache read tokens [M] | 287,744 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **44,931** |
| Thinking ratio [C] | 5.4% |
| Output efficiency [C] | 12.3% |
| Input cost [M] | $0.004892 |
| Output cost [M] | $0.005827 |
| Reasoning cost [M] | $0.002573 |
| Cache cost [M] | $0.019028 |
| **Total cost** | **$0.032320** |
| **Total energy [X]** | **~5369 J** |
| Solution density [C] | 0.006254 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000140 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0323  |  **Energy:** ~5369J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_mini_fp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 281 |
| Functions | 27 |
| Classes | 5 |
| Functions/file | 3.9 |
| Classes/file | 0.7 |
| Avg lines/file | 40 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 27 |
| Decorators | 18 |
| Test files | 2 |
| Test file rate | 29% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 3 |
| Failed | 0 |
| Errors | 0 |
| Total | 3 |
| Pass rate | 100% |
| Duration | 3.3s |
