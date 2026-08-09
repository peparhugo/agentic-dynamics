# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Python Flask URL shortener: rate limit & analytics...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:45:48

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.73) with moderate resource use ($0.0100, ~2358J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 3.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 32% (6/19 tests) [M] |
| Constraint satisfaction [H] | 83% (5/6 constraints) |
| Lines of code [M] | 375 |
| Cyclomatic complexity [C] | 75.0 |
| Code quality [H] | 0.267 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.728** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,653 |
| Completion tokens [M] | 5,241 |
| Reasoning tokens [M] | 638 |
| Cache read tokens [M] | 67,584 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **16,532** |
| Thinking ratio [C] | 3.9% |
| Output efficiency [C] | 31.7% |
| Input cost [M] | $0.001580 |
| Output cost [M] | $0.003167 |
| Reasoning cost [M] | $0.000049 |
| Cache cost [M] | $0.005198 |
| **Total cost** | **$0.009994** |
| **Total energy [X]** | **~2358 J** |
| Solution density [C] | 0.022683 LOC/tok |
| Correctness/$ [C] | 55 |
| Quality/J [C] | 0.000309 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 32%  |  **Cost:** $0.0100  |  **Energy:** ~2358J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_zbc1mgbx/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 375 |
| Functions | 42 |
| Classes | 1 |
| Functions/file | 21.0 |
| Classes/file | 0.5 |
| Avg lines/file | 188 |
| Type hints | 20% |
| Docstrings | 7% |
| Error handlers | 2 |
| Imports | 18 |
| Decorators | 12 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 6 |
| Failed | 13 |
| Errors | 0 |
| Total | 19 |
| Pass rate | 32% |
| Duration | 0.8s |
