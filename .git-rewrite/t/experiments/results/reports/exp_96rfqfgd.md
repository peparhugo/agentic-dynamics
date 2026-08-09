# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:15:09

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.726

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0151, ~4899J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.739 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.351 |
| Thinking ratio [C] | 24.6% |
| Quality/$ [C] | 66 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 713 |
| Cyclomatic complexity [C] | 60.0 |
| Code quality [H] | 0.140 |
| Novelty vs baseline [H] | 0.971 |
| **Composite [H]** | **0.497** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6,588 |
| Completion tokens [M] | 8,760 |
| Reasoning tokens [M] | 5,015 |
| Cache read tokens [M] | 63,872 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,363** |
| Thinking ratio [C] | 24.6% |
| Output efficiency [C] | 43.0% |
| Input cost [M] | $0.001274 |
| Output cost [M] | $0.006901 |
| Reasoning cost [M] | $0.000503 |
| Cache cost [M] | $0.006404 |
| **Total cost** | **$0.015082** |
| **Total energy [X]** | **~4899 J** |
| Solution density [C] | 0.035014 LOC/tok |
| Correctness/$ [C] | 38 |
| Quality/J [C] | 0.000101 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0151  |  **Energy:** ~4899J  |  **Thinking:** 25%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_96rfqfgd/session.jsonl)
- [Generated code](./exp_96rfqfgd/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 690 |
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
