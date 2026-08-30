# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [inject_alien_vocab_s0.5] process_perturbation_resample...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:27

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.921

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.4423, ~4324J, 1% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 1.2% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 452 |
| Cyclomatic complexity [C] | 73.0 |
| Code quality [H] | 0.221 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.598** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 27,396 |
| Completion tokens [M] | 8,389 |
| Reasoning tokens [M] | 432 |
| Cache read tokens [M] | 81,408 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **36,217** |
| Thinking ratio [C] | 1.2% |
| Output efficiency [C] | 23.2% |
| Input cost [C] | $0.136980 |
| Output cost [C] | $0.251670 |
| Reasoning cost [C] | $0.012960 |
| Cache cost [C] | $0.040704 |
| **Total cost** | **$0.442314** |
| **Total energy [X]** | **~4324 J** |
| Solution density [C] | 0.012480 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000138 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.4423  |  **Energy:** ~4324J  |  **Thinking:** 1%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_j3ze0rh7/session.jsonl)
- [Generated code](./exp_j3ze0rh7/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 452 |
| Functions | 43 |
| Classes | 1 |
| Functions/file | 10.8 |
| Classes/file | 0.2 |
| Avg lines/file | 113 |
| Type hints | 35% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 18 |
| Decorators | 15 |
| Test files | 2 |
| Test file rate | 50% |
| Parse errors | 0 |
