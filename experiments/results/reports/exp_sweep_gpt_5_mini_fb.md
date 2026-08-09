# Game Report: baseline-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:baseline:forced] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:40:45

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.650

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.62) with moderate resource use ($0.0271, ~3960J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 10.1% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (4/4 tests) [M] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 227 |
| Cyclomatic complexity [C] | 41.0 |
| Code quality [H] | 0.441 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.622** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 19,613 |
| Completion tokens [M] | 4,770 |
| Reasoning tokens [M] | 2,752 |
| Cache read tokens [M] | 287,488 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,135** |
| Thinking ratio [C] | 10.1% |
| Output efficiency [C] | 17.6% |
| Input cost [M] | $0.002381 |
| Output cost [M] | $0.004632 |
| Reasoning cost [M] | $0.002673 |
| Cache cost [M] | $0.017449 |
| **Total cost** | **$0.027134** |
| **Total energy [X]** | **~3960 J** |
| Solution density [C] | 0.008366 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000157 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0271  |  **Energy:** ~3960J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_mini_fb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 227 |
| Functions | 20 |
| Classes | 3 |
| Functions/file | 10.0 |
| Classes/file | 1.5 |
| Avg lines/file | 114 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 9 |
| Decorators | 12 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,770 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0476 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 4 |
| Failed | 0 |
| Errors | 0 |
| Total | 4 |
| Pass rate | 100% |
| Duration | 1.6s |
