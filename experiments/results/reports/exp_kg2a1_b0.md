# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Building and testing a URL shortener in Flask...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:58:32

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.67) with moderate resource use ($0.0109, ~2572J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 3.8% |
| Quality/$ | 102 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 96% (22/23 tests) |
| Constraint satisfaction | 67% (4/6 constraints) |
| Lines of code | 444 |
| Cyclomatic complexity | 53.0 |
| Code quality | 0.225 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.670** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,332 |
| Completion tokens | 6,256 |
| Reasoning tokens | 652 |
| **Total tokens** | **17,240** |
| Thinking ratio | 3.8% |
| Output efficiency | 36.3% |
| Input cost | $0.002790 |
| Output cost | $0.006882 |
| Reasoning cost | $0.000091 |
| **Total cost** | **$0.010950** |
| **Total energy** | **~2572 J** |
| Solution density | 0.025754 LOC/tok |
| Correctness/$ | 102 |
| Quality/J | 0.000261 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 96%  |  **Cost:** $0.0109  |  **Energy:** ~2572J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_kg2a1_b0/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 444 |
| Functions | 51 |
| Classes | 8 |
| Functions/file | 8.5 |
| Classes/file | 1.3 |
| Avg lines/file | 74 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 1 |
| Imports | 31 |
| Decorators | 8 |
| Test files | 1 |
| Test file rate | 17% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 22 |
| Failed | 1 |
| Errors | 0 |
| Total | 23 |
| Pass rate | 96% |
| Duration | 2.2s |
