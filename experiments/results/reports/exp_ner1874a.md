# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** openai/gpt-5  |  **Task:** [remove_critical_constraint_s0.5_r1] cd_openai_GPT_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:28:43

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.838

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.71) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0762, ~2800J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.706 |
| Architecture div [H] | 0.750 |
| Structure div [H] | 0.380 |
| Thinking ratio [C] | 4.1% |
| Quality/$ [C] | 13 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 241 |
| Cyclomatic complexity [C] | 45.0 |
| Code quality [H] | 0.415 |
| Novelty vs baseline [H] | 0.973 |
| **Composite [H]** | **0.879** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18,964 |
| Completion tokens [M] | 3,615 |
| Reasoning tokens [M] | 960 |
| Cache read tokens [M] | 54,016 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,539** |
| Thinking ratio [C] | 4.1% |
| Output efficiency [C] | 15.4% |
| Input cost [M] | $0.017502 |
| Output cost [M] | $0.026691 |
| Reasoning cost [M] | $0.007088 |
| Cache cost [M] | $0.024926 |
| **Total cost** | **$0.076207** |
| **Total energy [X]** | **~2800 J** |
| Solution density [C] | 0.010238 LOC/tok |
| Correctness/$ [C] | 10 |
| Quality/J [C] | 0.000314 |

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
