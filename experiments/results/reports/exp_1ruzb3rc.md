# Game Report: std_final-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [std_final] gpt-5-nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:39:40

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.739

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.55) with moderate resource use ($0.0059, ~4735J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.429 |
| Architecture div | 0.333 |
| Structure div | 0.154 |
| Thinking ratio | 21.6% |
| Quality/$ | 96 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (5/5 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 216 |
| Cyclomatic complexity | 40.0 |
| Code quality | 0.463 |
| Novelty vs baseline | 0.833 |
| **Composite** | **0.548** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12,971 |
| Completion tokens | 5,612 |
| Reasoning tokens | 5,120 |
| **Total tokens** | **23,703** |
| Thinking ratio | 21.6% |
| Output efficiency | 23.7% |
| Input cost | $0.003502 |
| Output cost | $0.006173 |
| Reasoning cost | $0.000717 |
| **Total cost** | **$0.005871** |
| **Total energy** | **~4735 J** |
| Solution density | 0.009113 LOC/tok |
| Correctness/$ | 67 |
| Quality/J | 0.000116 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0059  |  **Energy:** ~4735J  |  **Thinking:** 22%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_1ruzb3rc/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 216 |
| Functions | 25 |
| Classes | 1 |
| Functions/file | 12.5 |
| Classes/file | 0.5 |
| Avg lines/file | 108 |
| Type hints | 68% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 14 |
| Decorators | 6 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 5,612 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0385 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 5 |
| Failed | 0 |
| Errors | 0 |
| Total | 5 |
| Pass rate | 100% |
| Duration | 1.7s |
