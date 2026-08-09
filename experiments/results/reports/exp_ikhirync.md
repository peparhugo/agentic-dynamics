# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:34:53

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0159, ~4083J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.735 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.336 |
| Thinking ratio [C] | 7.8% |
| Quality/$ [C] | 63 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 700 |
| Cyclomatic complexity [C] | 52.0 |
| Code quality [H] | 0.143 |
| Novelty vs baseline [H] | 0.970 |
| **Composite [H]** | **0.497** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,037 |
| Completion tokens [M] | 10,679 |
| Reasoning tokens [M] | 1,753 |
| Cache read tokens [M] | 205,440 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,469** |
| Thinking ratio [C] | 7.8% |
| Output efficiency [C] | 47.5% |
| Input cost [M] | $0.000993 |
| Output cost [M] | $0.004304 |
| Reasoning cost [M] | $0.000090 |
| Cache cost [M] | $0.010539 |
| **Total cost** | **$0.015927** |
| **Total energy [X]** | **~4083 J** |
| Solution density [C] | 0.031154 LOC/tok |
| Correctness/$ [C] | 18 |
| Quality/J [C] | 0.000122 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0159  |  **Energy:** ~4083J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ikhirync/session.jsonl)
- [Generated code](./exp_ikhirync/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 19 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1040 |
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
