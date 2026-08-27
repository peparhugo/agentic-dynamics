# Game Report: exp__n7sboft-baseline

**Model:** openai/gpt-5.6-sol  |  **Task:** [baseline] process_perturbation_resample...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:42

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.916

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.3905, ~3564J, 3% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 3.1% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 367 |
| Cyclomatic complexity [C] | 47.0 |
| Code quality [H] | 0.272 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.565** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,872 |
| Completion tokens [M] | 6,455 |
| Reasoning tokens [M] | 872 |
| Cache read tokens [M] | 132,608 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **28,199** |
| Thinking ratio [C] | 3.1% |
| Output efficiency [C] | 22.9% |
| Input cost [C] | $0.104360 |
| Output cost [C] | $0.193650 |
| Reasoning cost [C] | $0.026160 |
| Cache cost [C] | $0.066304 |
| **Total cost** | **$0.390474** |
| **Total energy [X]** | **~3564 J** |
| Solution density [C] | 0.013015 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000159 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.3905  |  **Energy:** ~3564J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp__n7sboft/session.jsonl)
- [Generated code](./exp__n7sboft/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 367 |
| Functions | 31 |
| Classes | 2 |
| Functions/file | 4.4 |
| Classes/file | 0.3 |
| Avg lines/file | 52 |
| Type hints | 35% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 29 |
| Decorators | 10 |
| Test files | 2 |
| Test file rate | 29% |
| Parse errors | 0 |
