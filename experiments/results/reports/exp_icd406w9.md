# Game Report: invert_constraint_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:25:56

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.65) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.1651, ~3394J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.654 |
| Architecture div [H] | 0.750 |
| Structure div [H] | 0.229 |
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
| Lines of code [M] | 747 |
| Cyclomatic complexity [C] | 112.0 |
| Code quality [H] | 0.134 |
| Novelty vs baseline [H] | 0.952 |
| **Composite [H]** | **0.605** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16 |
| Completion tokens [M] | 14,749 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 116,318 |
| Cache write tokens [M] | 24,895 |
| **Total tokens** | **14,765** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000160 |
| Output cost [M] | $0.737450 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.427506 |
| **Total cost** | **$1.165116** |
| **Total energy [X]** | **~3394 J** |
| Solution density [C] | 0.050593 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000178 |

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
