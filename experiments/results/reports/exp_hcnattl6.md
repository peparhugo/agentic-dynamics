# Game Report: exp_hcnattl6-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT auth and pytest...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:57:17

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.765

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.0210, ~5219J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.1% |
| Quality/$ | 49 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 78% (14/18 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 1070 |
| Cyclomatic complexity | 141.0 |
| Code quality | 0.093 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.701** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12,519 |
| Completion tokens | 15,260 |
| Reasoning tokens | 1,506 |
| **Total tokens** | **29,285** |
| Thinking ratio | 5.1% |
| Output efficiency | 52.1% |
| Input cost | $0.003380 |
| Output cost | $0.016786 |
| Reasoning cost | $0.000211 |
| **Total cost** | **$0.020964** |
| **Total energy** | **~5219 J** |
| Solution density | 0.036537 LOC/tok |
| Correctness/$ | 49 |
| Quality/J | 0.000134 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 78%  |  **Cost:** $0.0210  |  **Energy:** ~5219J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_hcnattl6/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 19 |
| Total lines (Py) | 1070 |
| Functions | 109 |
| Classes | 14 |
| Functions/file | 5.7 |
| Classes/file | 0.7 |
| Avg lines/file | 56 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 33 |
| Decorators | 32 |
| Test files | 4 |
| Test file rate | 21% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 14 |
| Failed | 4 |
| Errors | 47 |
| Total | 18 |
| Pass rate | 78% |
| Duration | 12.0s |
