# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** openai/gpt-5  |  **Task:** [remove_critical_constraint_s0.5_r1] cd_openai_GPT_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:02

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.838

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.71) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0762, ~2800J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.706 |
| Architecture div | 0.750 |
| Structure div | 0.380 |
| Thinking ratio | 4.1% |
| Quality/$ | 13 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 100% (7/7 constraints) |
| Lines of code | 241 |
| Cyclomatic complexity | 45.0 |
| Code quality | 0.415 |
| Novelty vs baseline | 0.973 |
| **Composite** | **0.879** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18,964 |
| Completion tokens | 3,615 |
| Reasoning tokens | 960 |
| **Total tokens** | **23,539** |
| Thinking ratio | 4.1% |
| Output efficiency | 15.4% |
| **Total cost** | **$0.076207** |
| **Total energy** | **~2800 J** |
| Solution density | 0.010238 LOC/tok |
| Correctness/$ | 108 |
| Quality/J | 0.000314 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0762  |  **Energy:** ~2800J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ner1874a/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 241 |
| Functions | 20 |
| Classes | 5 |
| Functions/file | 2.9 |
| Classes/file | 0.7 |
| Avg lines/file | 34 |
| Type hints | 30% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 31 |
| Decorators | 25 |
| Test files | 2 |
| Test file rate | 29% |
| Parse errors | 0 |
