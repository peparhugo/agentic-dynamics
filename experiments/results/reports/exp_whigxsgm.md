# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:35:10

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.761

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.98, correctness=80%). Cost: $0.1685, ~4568J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.703 |
| Architecture div [H] | 0.667 |
| Structure div [H] | 0.470 |
| Thinking ratio [C] | 8.3% |
| Quality/$ [C] | 6 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 473 |
| Cyclomatic complexity [C] | 91.0 |
| Code quality [H] | 0.211 |
| Novelty vs baseline [H] | 0.985 |
| **Composite [H]** | **0.556** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16,906 |
| Completion tokens [M] | 9,143 |
| Reasoning tokens [M] | 2,368 |
| Cache read tokens [M] | 257,920 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **28,417** |
| Thinking ratio [C] | 8.3% |
| Output efficiency [C] | 32.2% |
| Input cost [M] | $0.011970 |
| Output cost [M] | $0.051789 |
| Reasoning cost [M] | $0.013413 |
| Cache cost [M] | $0.091310 |
| **Total cost** | **$0.168483** |
| **Total energy [X]** | **~4568 J** |
| Solution density [C] | 0.016645 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000122 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.1685  |  **Energy:** ~4568J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_whigxsgm/session.jsonl)
- [Generated code](./exp_whigxsgm/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 448 |
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
