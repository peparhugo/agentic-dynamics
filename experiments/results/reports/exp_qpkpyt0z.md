# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:02:44

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.832

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0168, ~4320J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.743 |
| Architecture div | 0.833 |
| Structure div | 0.398 |
| Thinking ratio | 6.3% |
| Quality/$ | 59 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 948 |
| Cyclomatic complexity | 70.0 |
| Code quality | 0.105 |
| Novelty vs baseline | 0.966 |
| **Composite** | **0.602** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 7,436 |
| Completion tokens | 13,346 |
| Reasoning tokens | 1,395 |
| **Total tokens** | **22,177** |
| Thinking ratio | 6.3% |
| Output efficiency | 60.2% |
| Input cost | $0.002008 |
| Output cost | $0.014681 |
| Reasoning cost | $0.000195 |
| **Total cost** | **$0.016755** |
| **Total energy** | **~4320 J** |
| Solution density | 0.042747 LOC/tok |
| Correctness/$ | 59 |
| Quality/J | 0.000139 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0168  |  **Energy:** ~4320J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_qpkpyt0z/session.jsonl)
- [Generated code](./exp_qpkpyt0z/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 28 |
| JS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1439 |
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
