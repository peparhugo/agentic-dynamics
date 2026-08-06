# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:28

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.65) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $0.8493, ~2414J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.646 |
| Architecture div | 0.750 |
| Structure div | 0.198 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 654 |
| Cyclomatic complexity | 90.0 |
| Code quality | 0.153 |
| Novelty vs baseline | 0.955 |
| **Composite** | **0.497** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12 |
| Completion tokens | 10,490 |
| Reasoning tokens | 0 |
| **Total tokens** | **10,502** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$0.849264** |
| **Total energy** | **~2414 J** |
| Solution density | 0.062274 LOC/tok |
| Correctness/$ | 69 |
| Quality/J | 0.000206 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.8493  |  **Energy:** ~2414J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_9tfs606s/session.jsonl)
- [Generated code](./exp_9tfs606s/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 638 |
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
