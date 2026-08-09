# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:45:55

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.763

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0200, ~4860J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.734 |
| Architecture div [H] | 0.875 |
| Structure div [H] | 0.311 |
| Thinking ratio [C] | 6.1% |
| Quality/$ [C] | 50 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 742 |
| Cyclomatic complexity [C] | 54.0 |
| Code quality [H] | 0.135 |
| Novelty vs baseline [H] | 0.967 |
| **Composite [H]** | **0.495** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,865 |
| Completion tokens [M] | 14,049 |
| Reasoning tokens [M] | 1,616 |
| Cache read tokens [M] | 461,056 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **26,530** |
| Thinking ratio [C] | 6.1% |
| Output efficiency [C] | 53.0% |
| Input cost [M] | $0.000706 |
| Output cost [M] | $0.003721 |
| Reasoning cost [M] | $0.000054 |
| Cache cost [M] | $0.015544 |
| **Total cost** | **$0.020026** |
| **Total energy [X]** | **~4860 J** |
| Solution density [C] | 0.027968 LOC/tok |
| Correctness/$ [C] | 10 |
| Quality/J [C] | 0.000102 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0200  |  **Energy:** ~4860J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ze0y99pc/session.jsonl)
- [Generated code](./exp_ze0y99pc/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
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
