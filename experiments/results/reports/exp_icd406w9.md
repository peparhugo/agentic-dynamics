# Game Report: invert_constraint_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:56

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.65) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.1651, ~3394J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.654 |
| Architecture div | 0.750 |
| Structure div | 0.229 |
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
| Lines of code | 747 |
| Cyclomatic complexity | 112.0 |
| Code quality | 0.134 |
| Novelty vs baseline | 0.952 |
| **Composite** | **0.605** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 16 |
| Completion tokens | 14,749 |
| Reasoning tokens | 0 |
| **Total tokens** | **14,765** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$1.165116** |
| **Total energy** | **~3394 J** |
| Solution density | 0.050593 LOC/tok |
| Correctness/$ | 62 |
| Quality/J | 0.000178 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $1.1651  |  **Energy:** ~3394J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_icd406w9/session.jsonl)
- [Generated code](./exp_icd406w9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 11 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 733 |
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
