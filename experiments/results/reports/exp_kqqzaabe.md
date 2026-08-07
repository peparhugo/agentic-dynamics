# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:22:20

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** WASTEFUL
**Score:** 0.326

**Verdict:** WASTEFUL — model burned 15,025 tokens ($0.0105, ~4126J, 46% thinking) achieving only 20% correctness. High reasoning overhead without convergence.

**Recommendation:** Reduce perturbation strength or avoid this operator class.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.823 |
| Architecture div [H] | 1.000 |
| Structure div [H] | 0.419 |
| Thinking ratio [C] | 46.2% |
| Quality/$ [C] | 95 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 20% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 32 |
| Cyclomatic complexity [C] | 1.0 |
| Code quality [H] | 0.983 |
| Novelty vs baseline [H] | 0.992 |
| **Composite [H]** | **0.415** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6,632 |
| Completion tokens [M] | 1,455 |
| Reasoning tokens [M] | 6,938 |
| Cache read tokens [M] | 88,576 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **15,025** |
| Thinking ratio [C] | 46.2% |
| Output efficiency [C] | 9.7% |
| Input cost [M] | $0.001122 |
| Output cost [M] | $0.001003 |
| Reasoning cost [M] | $0.000609 |
| Cache cost [M] | $0.007773 |
| **Total cost** | **$0.010508** |
| **Total energy [X]** | **~4126 J** |
| Solution density [C] | 0.002130 LOC/tok |
| Correctness/$ [C] | 12 |
| Quality/J [C] | 0.000101 |

---

## Headline Metric
**Strategy:** WASTEFUL  |  **Correctness:** 20%  |  **Cost:** $0.0105  |  **Energy:** ~4126J  |  **Thinking:** 46%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_kqqzaabe/session.jsonl)
- [Generated code](./exp_kqqzaabe/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 1 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 31 |
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
