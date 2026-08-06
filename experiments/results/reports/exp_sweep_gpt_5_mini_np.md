# Game Report: perturbed-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:perturbed:natural] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:32:27

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.656

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.64) with moderate resource use ($0.0284, ~3978J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 6.8% |
| Quality/$ [C] | 35 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 75% (3/4 tests) [M] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 342 |
| Cyclomatic complexity [C] | 68.0 |
| Code quality [H] | 0.292 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.636** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18,472 |
| Completion tokens [M] | 7,076 |
| Reasoning tokens [M] | 1,856 |
| Cache read tokens [M] | 235,648 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,404** |
| Thinking ratio [C] | 6.8% |
| Output efficiency [C] | 25.8% |
| Input cost [M] | $0.002523 |
| Output cost [M] | $0.007731 |
| Reasoning cost [M] | $0.002028 |
| Cache cost [M] | $0.016092 |
| **Total cost** | **$0.028373** |
| **Total energy [X]** | **~3978 J** |
| Solution density [C] | 0.012480 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000160 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 75%  |  **Cost:** $0.0284  |  **Energy:** ~3978J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_mini_np/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 5 |
| Total lines (Py) | 342 |
| Functions | 31 |
| Classes | 4 |
| Functions/file | 6.2 |
| Classes/file | 0.8 |
| Avg lines/file | 68 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 29 |
| Decorators | 18 |
| Test files | 2 |
| Test file rate | 40% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,076 |
| Python files | 5 |
| Non-Python files | 0 |
| Code density | 0.0483 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 3 |
| Failed | 1 |
| Errors | 0 |
| Total | 4 |
| Pass rate | 75% |
| Duration | 4.1s |
