# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:47:17

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.837

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.98, correctness=100%). Cost: $0.1594, ~4031J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.702 |
| Architecture div | 0.667 |
| Structure div | 0.467 |
| Thinking ratio | 5.1% |
| Quality/$ | 6 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 469 |
| Cyclomatic complexity | 65.0 |
| Code quality | 0.213 |
| Novelty vs baseline | 0.983 |
| **Composite** | **0.540** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18,034 |
| Completion tokens | 8,375 |
| Reasoning tokens | 1,408 |
| **Total tokens** | **27,817** |
| Thinking ratio | 5.1% |
| Output efficiency | 30.1% |
| **Total cost** | **$0.159429** |
| **Total energy** | **~4031 J** |
| Solution density | 0.016860 LOC/tok |
| Correctness/$ | 70 |
| Quality/J | 0.000134 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.1594  |  **Energy:** ~4031J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_dalqefiq/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 16 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 983 |
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
