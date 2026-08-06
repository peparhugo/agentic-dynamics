# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:24:11

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.842

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.62) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.3579, ~3870J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.619 |
| Architecture div [H] | 0.636 |
| Structure div [H] | 0.265 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 1015 |
| Cyclomatic complexity [C] | 127.0 |
| Code quality [H] | 0.099 |
| Novelty vs baseline [H] | 0.949 |
| **Composite [H]** | **0.598** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 24 |
| Completion tokens [M] | 16,816 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 189,412 |
| Cache write tokens [M] | 26,192 |
| **Total tokens** | **16,840** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000240 |
| Output cost [M] | $0.840800 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.516812 |
| **Total cost** | **$1.357852** |
| **Total energy [X]** | **~3870 J** |
| Solution density [C] | 0.060273 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000154 |

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
