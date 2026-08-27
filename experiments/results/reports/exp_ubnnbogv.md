# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-flash  |  **Task:** [inject_competing_goal_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:05

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.814

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.0125, ~12341J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 36.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 1172 |
| Cyclomatic complexity [C] | 185.0 |
| Code quality [H] | 0.085 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.699** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,255 |
| Completion tokens [M] | 17,969 |
| Reasoning tokens [M] | 15,889 |
| Cache read tokens [M] | 620,288 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **43,113** |
| Thinking ratio [C] | 36.9% |
| Output efficiency [C] | 41.7% |
| Input cost [M] | $0.000887 |
| Output cost [M] | $0.005166 |
| Reasoning cost [M] | $0.004568 |
| Cache cost [M] | $0.001891 |
| **Total cost** | **$0.012513** |
| **Total energy [X]** | **~12341 J** |
| Solution density [C] | 0.027184 LOC/tok |
| Correctness/$ [C] | 35 |
| Quality/J [C] | 0.000057 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0125  |  **Energy:** ~12341J  |  **Thinking:** 37%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ubnnbogv/session.jsonl)
- [Generated code](./exp_ubnnbogv/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 20 |
| Total lines (Py) | 1172 |
| Functions | 142 |
| Classes | 5 |
| Functions/file | 7.1 |
| Classes/file | 0.2 |
| Avg lines/file | 59 |
| Type hints | 0% |
| Docstrings | 1% |
| Error handlers | 10 |
| Imports | 55 |
| Decorators | 34 |
| Test files | 8 |
| Test file rate | 40% |
| Parse errors | 0 |
