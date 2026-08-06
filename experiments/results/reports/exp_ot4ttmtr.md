# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask URL shortener: collision-resistant+analytics...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:01:25

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.761

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.68) with moderate resource use ($0.0104, ~2559J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.2% |
| Quality/$ | 114 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 63% (22/35 tests) |
| Constraint satisfaction | 67% (4/6 constraints) |
| Lines of code | 386 |
| Cyclomatic complexity | 36.0 |
| Code quality | 0.259 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.677** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,062 |
| Completion tokens | 5,637 |
| Reasoning tokens | 1,143 |
| **Total tokens** | **15,842** |
| Thinking ratio | 7.2% |
| Output efficiency | 35.6% |
| Input cost | $0.002447 |
| Output cost | $0.006201 |
| Reasoning cost | $0.000160 |
| **Total cost** | **$0.010362** |
| **Total energy** | **~2559 J** |
| Solution density | 0.024366 LOC/tok |
| Correctness/$ | 114 |
| Quality/J | 0.000265 |

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
| Duration | 3.3s |
