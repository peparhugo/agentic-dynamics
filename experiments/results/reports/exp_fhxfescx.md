# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:09

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.842

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.62) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.3579, ~3870J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.619 |
| Architecture div | 0.636 |
| Structure div | 0.265 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 1015 |
| Cyclomatic complexity | 127.0 |
| Code quality | 0.099 |
| Novelty vs baseline | 0.949 |
| **Composite** | **0.598** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 24 |
| Completion tokens | 16,816 |
| Reasoning tokens | 0 |
| **Total tokens** | **16,840** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$1.357852** |
| **Total energy** | **~3870 J** |
| Solution density | 0.060273 LOC/tok |
| Correctness/$ | 54 |
| Quality/J | 0.000154 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $1.3579  |  **Energy:** ~3870J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_fhxfescx/session.jsonl)
- [Generated code](./exp_fhxfescx/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 13 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 995 |
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
