# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:33:00

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.67) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $1.3343, ~3871J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.670 |
| Architecture div [H] | 0.750 |
| Structure div [H] | 0.281 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (3/3 tests) [M] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 907 |
| Cyclomatic complexity [C] | 147.0 |
| Code quality [H] | 0.110 |
| Novelty vs baseline [H] | 0.953 |
| **Composite [H]** | **0.531** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20 |
| Completion tokens [M] | 16,825 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 152,983 |
| Cache write tokens [M] | 27,193 |
| **Total tokens** | **16,845** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000200 |
| Output cost [M] | $0.841250 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.492895 |
| **Total cost** | **$1.334345** |
| **Total energy [X]** | **~3871 J** |
| Solution density [C] | 0.053844 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000137 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $1.3343  |  **Energy:** ~3871J  |  **Thinking:** 0%

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


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 3 |
| Failed | 0 |
| Errors | 0 |
| Total | 3 |
| Pass rate | 100% |
| Duration | 4.7s |
