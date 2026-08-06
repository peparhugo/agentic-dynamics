# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:24

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.67) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $1.3343, ~3871J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.670 |
| Architecture div | 0.750 |
| Structure div | 0.281 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 907 |
| Cyclomatic complexity | 147.0 |
| Code quality | 0.110 |
| Novelty vs baseline | 0.953 |
| **Composite** | **0.574** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 20 |
| Completion tokens | 16,825 |
| Reasoning tokens | 0 |
| **Total tokens** | **16,845** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$1.334345** |
| **Total energy** | **~3871 J** |
| Solution density | 0.053844 LOC/tok |
| Correctness/$ | 43 |
| Quality/J | 0.000148 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $1.3343  |  **Energy:** ~3871J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_gfjpa3ah/session.jsonl)
- [Generated code](./exp_gfjpa3ah/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 11 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 889 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
