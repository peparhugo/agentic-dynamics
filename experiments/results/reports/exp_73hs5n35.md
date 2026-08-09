# Game Report: shift_framing_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [shift_framing_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:21:58

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.63) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $1.0062, ~2650J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.627 |
| Architecture div [H] | 0.727 |
| Structure div [H] | 0.167 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 678 |
| Cyclomatic complexity [C] | 105.0 |
| Code quality [H] | 0.147 |
| Novelty vs baseline [H] | 0.955 |
| **Composite [H]** | **0.538** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 22 |
| Completion tokens [M] | 11,516 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 153,975 |
| Cache write tokens [M] | 22,095 |
| **Total tokens** | **11,538** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000220 |
| Output cost [M] | $0.575800 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.430162 |
| **Total cost** | **$1.006182** |
| **Total energy [X]** | **~2650 J** |
| Solution density [C] | 0.058762 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000203 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $1.0062  |  **Energy:** ~2650J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_73hs5n35/session.jsonl)
- [Generated code](./exp_73hs5n35/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 666 |
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
