# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:29:21

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.64) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.8753, ~5315J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.643 |
| Architecture div [H] | 0.667 |
| Structure div [H] | 0.302 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 1212 |
| Cyclomatic complexity [C] | 136.0 |
| Code quality [H] | 0.083 |
| Novelty vs baseline [H] | 0.953 |
| **Composite [H]** | **0.638** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 28 |
| Completion tokens [M] | 23,099 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 271,294 |
| Cache write tokens [M] | 35,903 |
| **Total tokens** | **23,127** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000280 |
| Output cost [M] | $1.154950 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.720082 |
| **Total cost** | **$1.875312** |
| **Total energy [X]** | **~5315 J** |
| Solution density [C] | 0.052406 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000120 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $1.8753  |  **Energy:** ~5315J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_oylan6wf/session.jsonl)
- [Generated code](./exp_oylan6wf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 24 |
| JS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1988 |
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
