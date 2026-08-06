# Game Report: perturbed-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:perturbed:forced] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:04:40

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.72) with moderate resource use ($0.3937, ~1938J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 8.0% |
| Quality/$ | 126 |
| Quality/J | 0.0005 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (19/19 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 477 |
| Cyclomatic complexity | 89.0 |
| Code quality | 0.210 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.724** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 27 |
| Completion tokens | 7,141 |
| Reasoning tokens | 625 |
| **Total tokens** | **7,793** |
| Thinking ratio | 8.0% |
| Output efficiency | 91.6% |
| Input cost | $0.000007 |
| Output cost | $0.007855 |
| Reasoning cost | $0.000088 |
| **Total cost** | **$0.393734** |
| **Total energy** | **~1938 J** |
| Solution density | 0.061209 LOC/tok |
| Correctness/$ | 126 |
| Quality/J | 0.000374 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3937  |  **Energy:** ~1938J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_6_fp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 477 |
| Functions | 50 |
| Classes | 4 |
| Functions/file | 25.0 |
| Classes/file | 2.0 |
| Avg lines/file | 238 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 12 |
| Decorators | 33 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 19 |
| Failed | 0 |
| Errors | 0 |
| Total | 19 |
| Pass rate | 100% |
| Duration | 6.4s |
