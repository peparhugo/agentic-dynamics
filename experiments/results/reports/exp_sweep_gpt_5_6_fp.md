# Game Report: perturbed-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:perturbed:forced] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:40:39

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.72) with moderate resource use ($0.3937, ~1938J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 8.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (19/19 tests) [M] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 477 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.210 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.724** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 27 |
| Completion tokens [M] | 7,141 |
| Reasoning tokens [M] | 625 |
| Cache read tokens [M] | 93,975 |
| Cache write tokens [M] | 18,181 |
| **Total tokens** | **7,793** |
| Thinking ratio [C] | 8.0% |
| Output efficiency [C] | 91.6% |
| Input cost [M] | $0.000073 |
| Output cost [M] | $0.154588 |
| Reasoning cost [M] | $0.013530 |
| Cache cost [M] | $0.225543 |
| **Total cost** | **$0.393734** |
| **Total energy [X]** | **~1938 J** |
| Solution density [C] | 0.061209 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000374 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3937  |  **Energy:** ~1938J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_6_fp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 477 |
| Functions | 50 |
| Classes | 4 |
| Functions/file | 25.0 |
| Classes/file | 2.0 |
| Avg lines/file | 238 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 12 |
| Decorators | 33 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 19 |
| Failed | 0 |
| Errors | 0 |
| Total | 19 |
| Pass rate | 100% |
| Duration | 6.5s |
