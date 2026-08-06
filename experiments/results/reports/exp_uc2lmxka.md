# Game Report: exp_uc2lmxka-baseline

**Model:** openai/gpt-5.6  |  **Task:** [baseline] frontier_gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:33:27

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.73) with moderate resource use ($0.4089, ~2002J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 5.3% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (11/11 tests) [M] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 455 |
| Cyclomatic complexity [C] | 72.0 |
| Code quality [H] | 0.220 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.726** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 39 |
| Completion tokens [M] | 7,797 |
| Reasoning tokens [M] | 437 |
| Cache read tokens [M] | 129,008 |
| Cache write tokens [M] | 15,556 |
| **Total tokens** | **8,273** |
| Thinking ratio [C] | 5.3% |
| Output efficiency [C] | 94.2% |
| Input cost [M] | $0.000099 |
| Output cost [M] | $0.157920 |
| Reasoning cost [M] | $0.008851 |
| Cache cost [M] | $0.242075 |
| **Total cost** | **$0.408944** |
| **Total energy [X]** | **~2002 J** |
| Solution density [C] | 0.054998 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000363 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.4089  |  **Energy:** ~2002J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_uc2lmxka/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 455 |
| Functions | 45 |
| Classes | 2 |
| Functions/file | 15.0 |
| Classes/file | 0.7 |
| Avg lines/file | 152 |
| Type hints | 50% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 19 |
| Decorators | 20 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 11 |
| Failed | 0 |
| Errors | 0 |
| Total | 11 |
| Pass rate | 100% |
| Duration | 4.0s |
