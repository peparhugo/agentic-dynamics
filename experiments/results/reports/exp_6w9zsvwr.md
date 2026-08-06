# Game Report: std_final-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [std_final] gpt-5.6-fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:43:00

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.825

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.96, correctness=100%). Cost: $0.6268, ~1498J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.746 |
| Architecture div | 0.857 |
| Structure div | 0.385 |
| Thinking ratio | 9.5% |
| Quality/$ | 167 |
| Quality/J | 0.0007 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (8/8 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 292 |
| Cyclomatic complexity | 32.0 |
| Code quality | 0.342 |
| Novelty vs baseline | 0.960 |
| **Composite** | **0.691** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 36 |
| Completion tokens | 5,349 |
| Reasoning tokens | 564 |
| **Total tokens** | **5,949** |
| Thinking ratio | 9.5% |
| Output efficiency | 89.9% |
| Input cost | $0.000010 |
| Output cost | $0.005884 |
| Reasoning cost | $0.000079 |
| **Total cost** | **$0.626804** |
| **Total energy** | **~1498 J** |
| Solution density | 0.049084 LOC/tok |
| Correctness/$ | 167 |
| Quality/J | 0.000461 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.6268  |  **Energy:** ~1498J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_6w9zsvwr/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 5 |
| Total lines (Py) | 292 |
| Functions | 26 |
| Classes | 0 |
| Functions/file | 5.2 |
| Classes/file | 0.0 |
| Avg lines/file | 58 |
| Type hints | 38% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 15 |
| Decorators | 8 |
| Test files | 2 |
| Test file rate | 40% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 8 |
| Failed | 0 |
| Errors | 0 |
| Total | 8 |
| Pass rate | 100% |
| Duration | 1.7s |
