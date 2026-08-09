# Game Report: std_final-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [std_final] gpt-5-nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:18:15

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.739

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.55) with moderate resource use ($0.0059, ~4735J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.429 |
| Architecture div [H] | 0.333 |
| Structure div [H] | 0.154 |
| Thinking ratio [C] | 21.6% |
| Quality/$ [C] | 170 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (5/5 tests) [M] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 216 |
| Cyclomatic complexity [C] | 40.0 |
| Code quality [H] | 0.463 |
| Novelty vs baseline [H] | 0.833 |
| **Composite [H]** | **0.548** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,971 |
| Completion tokens [M] | 5,612 |
| Reasoning tokens [M] | 5,120 |
| Cache read tokens [M] | 185,984 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,703** |
| Thinking ratio [C] | 21.6% |
| Output efficiency [C] | 23.7% |
| Input cost [M] | $0.000397 |
| Output cost [M] | $0.001374 |
| Reasoning cost [M] | $0.001254 |
| Cache cost [M] | $0.002846 |
| **Total cost** | **$0.005871** |
| **Total energy [X]** | **~4735 J** |
| Solution density [C] | 0.009113 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000116 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0059  |  **Energy:** ~4735J  |  **Thinking:** 22%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_1ruzb3rc/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 216 |
| Functions | 25 |
| Classes | 1 |
| Functions/file | 12.5 |
| Classes/file | 0.5 |
| Avg lines/file | 108 |
| Type hints | 68% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 14 |
| Decorators | 6 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 5,612 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0385 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 5 |
| Failed | 0 |
| Errors | 0 |
| Total | 5 |
| Pass rate | 100% |
| Duration | 1.1s |
