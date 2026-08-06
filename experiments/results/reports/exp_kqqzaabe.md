# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:49:56

---

## Strategy
**Classification:** WASTEFUL
**Score:** 0.326

**Verdict:** WASTEFUL — model burned 15,025 tokens ($0.0105, ~4126J, 46% thinking) achieving only 20% correctness. High reasoning overhead without convergence.

**Recommendation:** Reduce perturbation strength or avoid this operator class.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.823 |
| Architecture div | 1.000 |
| Structure div | 0.419 |
| Thinking ratio | 46.2% |
| Quality/$ | 95 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 20% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 32 |
| Cyclomatic complexity | 1.0 |
| Code quality | 0.983 |
| Novelty vs baseline | 0.992 |
| **Composite** | **0.415** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 6,632 |
| Completion tokens | 1,455 |
| Reasoning tokens | 6,938 |
| **Total tokens** | **15,025** |
| Thinking ratio | 46.2% |
| Output efficiency | 9.7% |
| **Total cost** | **$0.010508** |
| **Total energy** | **~4126 J** |
| Solution density | 0.002130 LOC/tok |
| Correctness/$ | 46 |
| Quality/J | 0.000101 |

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
