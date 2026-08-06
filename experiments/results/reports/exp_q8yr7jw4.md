# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:43

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.67) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.8610, ~5268J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.672 |
| Architecture div | 0.750 |
| Structure div | 0.288 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 1005 |
| Cyclomatic complexity | 134.0 |
| Code quality | 0.100 |
| Novelty vs baseline | 0.952 |
| **Composite** | **0.598** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 26 |
| Completion tokens | 22,897 |
| Reasoning tokens | 0 |
| **Total tokens** | **22,923** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$1.861028** |
| **Total energy** | **~5268 J** |
| Solution density | 0.043842 LOC/tok |
| Correctness/$ | 40 |
| Quality/J | 0.000114 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $1.8610  |  **Energy:** ~5268J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_q8yr7jw4/session.jsonl)
- [Generated code](./exp_q8yr7jw4/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 13 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 992 |
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
