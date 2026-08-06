# Game Report: perturbed-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:perturbed:natural] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:32:14

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.760

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.76) with moderate resource use ($0.4235, ~2264J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.5% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (9/9 tests) [M] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 618 |
| Cyclomatic complexity [C] | 73.0 |
| Code quality [H] | 0.162 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.757** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 30 |
| Completion tokens [M] | 8,426 |
| Reasoning tokens [M] | 689 |
| Cache read tokens [M] | 95,275 |
| Cache write tokens [M] | 16,368 |
| **Total tokens** | **9,145** |
| Thinking ratio [C] | 7.5% |
| Output efficiency [C] | 92.1% |
| Input cost [M] | $0.000083 |
| Output cost [M] | $0.186206 |
| Reasoning cost [M] | $0.015226 |
| Cache cost [M] | $0.222022 |
| **Total cost** | **$0.423538** |
| **Total energy [X]** | **~2264 J** |
| Solution density [C] | 0.067578 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000334 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.4235  |  **Energy:** ~2264J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_6_np/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 11 |
| Total lines (Py) | 618 |
| Functions | 58 |
| Classes | 5 |
| Functions/file | 5.3 |
| Classes/file | 0.5 |
| Avg lines/file | 56 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 48 |
| Decorators | 39 |
| Test files | 2 |
| Test file rate | 18% |
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
| Duration | 4.9s |
