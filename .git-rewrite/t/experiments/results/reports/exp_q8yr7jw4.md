# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:24:14

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.67) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.8610, ~5268J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.672 |
| Architecture div [H] | 0.750 |
| Structure div [H] | 0.288 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 1005 |
| Cyclomatic complexity [C] | 134.0 |
| Code quality [H] | 0.100 |
| Novelty vs baseline [H] | 0.952 |
| **Composite [H]** | **0.556** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 26 |
| Completion tokens [M] | 22,897 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 263,018 |
| Cache write tokens [M] | 36,232 |
| **Total tokens** | **22,923** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000260 |
| Output cost [M] | $1.144850 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.715918 |
| **Total cost** | **$1.861028** |
| **Total energy [X]** | **~5268 J** |
| Solution density [C] | 0.043842 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000105 |

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
