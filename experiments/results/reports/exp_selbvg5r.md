# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5.5  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_gather_gpt_5_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:04:28

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.839

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.71) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.3159, ~2859J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.715 |
| Architecture div | 0.750 |
| Structure div | 0.417 |
| Thinking ratio | 2.9% |
| Quality/$ | 96 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (9/9 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 288 |
| Cyclomatic complexity | 47.0 |
| Code quality | 0.347 |
| Novelty vs baseline | 0.966 |
| **Composite** | **0.822** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 16,911 |
| Completion tokens | 5,216 |
| Reasoning tokens | 652 |
| **Total tokens** | **22,779** |
| Thinking ratio | 2.9% |
| Output efficiency | 22.9% |
| Input cost | $0.004566 |
| Output cost | $0.005738 |
| Reasoning cost | $0.000091 |
| **Total cost** | **$0.315891** |
| **Total energy** | **~2859 J** |
| Solution density | 0.012643 LOC/tok |
| Correctness/$ | 96 |
| Quality/J | 0.000287 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.3159  |  **Energy:** ~2859J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_selbvg5r/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 288 |
| Functions | 35 |
| Classes | 1 |
| Functions/file | 11.7 |
| Classes/file | 0.3 |
| Avg lines/file | 96 |
| Type hints | 34% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 11 |
| Decorators | 17 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 9 |
| Failed | 0 |
| Errors | 0 |
| Total | 9 |
| Pass rate | 100% |
| Duration | 0.7s |
