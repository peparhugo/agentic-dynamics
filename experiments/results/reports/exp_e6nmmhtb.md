# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (manifold, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:19:13

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.831

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0146, ~3599J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.748 |
| Architecture div [H] | 0.875 |
| Structure div [H] | 0.357 |
| Thinking ratio [C] | 7.2% |
| Quality/$ [C] | 68 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 799 |
| Cyclomatic complexity [C] | 87.0 |
| Code quality [H] | 0.125 |
| Novelty vs baseline [H] | 0.969 |
| **Composite [H]** | **0.563** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,838 |
| Completion tokens [M] | 10,073 |
| Reasoning tokens [M] | 1,394 |
| Cache read tokens [M] | 347,008 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,305** |
| Thinking ratio [C] | 7.2% |
| Output efficiency [C] | 52.2% |
| Input cost [M] | $0.000500 |
| Output cost [M] | $0.002618 |
| Reasoning cost [M] | $0.000046 |
| Cache cost [M] | $0.011479 |
| **Total cost** | **$0.014644** |
| **Total energy [X]** | **~3599 J** |
| Solution density [C] | 0.041388 LOC/tok |
| Correctness/$ [C] | 16 |
| Quality/J [C] | 0.000157 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0146  |  **Energy:** ~3599J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_e6nmmhtb/session.jsonl)
- [Generated code](./exp_e6nmmhtb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 18 |
| JS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1260 |
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
