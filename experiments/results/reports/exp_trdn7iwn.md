# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:33:07

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.59) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $0.9862, ~2695J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.594 |
| Architecture div [H] | 0.636 |
| Structure div [H] | 0.177 |
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
| Lines of code [M] | 633 |
| Cyclomatic complexity [C] | 104.0 |
| Code quality [H] | 0.158 |
| Novelty vs baseline [H] | 0.954 |
| **Composite [H]** | **0.540** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18 |
| Completion tokens [M] | 11,709 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 123,749 |
| Cache write tokens [M] | 22,145 |
| **Total tokens** | **11,727** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000180 |
| Output cost [M] | $0.585450 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.400561 |
| **Total cost** | **$0.986191** |
| **Total energy [X]** | **~2695 J** |
| Solution density [C] | 0.053978 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000201 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.9862  |  **Energy:** ~2695J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_trdn7iwn/session.jsonl)
- [Generated code](./exp_trdn7iwn/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 622 |
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
