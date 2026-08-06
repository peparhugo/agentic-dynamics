# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask URL shortener with rate limiting and tests...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:05:11

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.821

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.69) with moderate resource use ($0.0064, ~1455J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 3.7% |
| Quality/$ | 189 |
| Quality/J | 0.0007 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 38% (6/16 tests) |
| Constraint satisfaction | 50% (3/6 constraints) |
| Lines of code | 227 |
| Cyclomatic complexity | 21.0 |
| Code quality | 0.591 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.693** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 7,412 |
| Completion tokens | 2,938 |
| Reasoning tokens | 397 |
| **Total tokens** | **10,747** |
| Thinking ratio | 3.7% |
| Output efficiency | 27.3% |
| Input cost | $0.002001 |
| Output cost | $0.003232 |
| Reasoning cost | $0.000056 |
| **Total cost** | **$0.006419** |
| **Total energy** | **~1455 J** |
| Solution density | 0.021122 LOC/tok |
| Correctness/$ | 189 |
| Quality/J | 0.000476 |

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
| Duration | 1.0s |
