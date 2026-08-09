# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask URL shortener with rate limiting and tests...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:41:09

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.821

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.69) with moderate resource use ($0.0064, ~1455J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 3.7% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 38% (6/16 tests) [M] |
| Constraint satisfaction [H] | 50% (3/6 constraints) |
| Lines of code [M] | 227 |
| Cyclomatic complexity [C] | 21.0 |
| Code quality [H] | 0.591 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.693** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,412 |
| Completion tokens [M] | 2,938 |
| Reasoning tokens [M] | 397 |
| Cache read tokens [M] | 81,024 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **10,747** |
| Thinking ratio [C] | 3.7% |
| Output efficiency [C] | 27.3% |
| Input cost [M] | $0.000772 |
| Output cost [M] | $0.001247 |
| Reasoning cost [M] | $0.000021 |
| Cache cost [M] | $0.004378 |
| **Total cost** | **$0.006419** |
| **Total energy [X]** | **~1455 J** |
| Solution density [C] | 0.021122 LOC/tok |
| Correctness/$ [C] | 60 |
| Quality/J [C] | 0.000476 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 38%  |  **Cost:** $0.0064  |  **Energy:** ~1455J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_tjlvdunl/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 227 |
| Functions | 29 |
| Classes | 0 |
| Functions/file | 14.5 |
| Classes/file | 0.0 |
| Avg lines/file | 114 |
| Type hints | 16% |
| Docstrings | 0% |
| Error handlers | 1 |
| Imports | 11 |
| Decorators | 10 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 6 |
| Failed | 10 |
| Errors | 0 |
| Total | 16 |
| Pass rate | 38% |
| Duration | 0.8s |
