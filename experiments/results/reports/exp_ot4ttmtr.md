# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask URL shortener: collision-resistant+analytics...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:29:10

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.761

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.68) with moderate resource use ($0.0104, ~2559J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.2% |
| Quality/$ [C] | 97 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 63% (22/35 tests) [M] |
| Constraint satisfaction [H] | 67% (4/6 constraints) |
| Lines of code [M] | 386 |
| Cyclomatic complexity [C] | 36.0 |
| Code quality [H] | 0.259 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.677** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,062 |
| Completion tokens [M] | 5,637 |
| Reasoning tokens [M] | 1,143 |
| Cache read tokens [M] | 143,872 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **15,842** |
| Thinking ratio [C] | 7.2% |
| Output efficiency [C] | 35.6% |
| Input cost [M] | $0.000876 |
| Output cost [M] | $0.002219 |
| Reasoning cost [M] | $0.000057 |
| Cache cost [M] | $0.007210 |
| **Total cost** | **$0.010362** |
| **Total energy [X]** | **~2559 J** |
| Solution density [C] | 0.024366 LOC/tok |
| Correctness/$ [C] | 35 |
| Quality/J [C] | 0.000265 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 63%  |  **Cost:** $0.0104  |  **Energy:** ~2559J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ot4ttmtr/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 386 |
| Functions | 48 |
| Classes | 9 |
| Functions/file | 24.0 |
| Classes/file | 4.5 |
| Avg lines/file | 193 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 14 |
| Decorators | 12 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 22 |
| Failed | 13 |
| Errors | 0 |
| Total | 35 |
| Pass rate | 63% |
| Duration | 2.3s |
