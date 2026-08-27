# Game Report: shift_framing_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [shift_framing_s0.5] process_perturbation_resample...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:47

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.912

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.4166, ~3797J, 4% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 4.2% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 390 |
| Cyclomatic complexity [C] | 39.0 |
| Code quality [H] | 0.256 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.605** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 21,552 |
| Completion tokens [M] | 6,479 |
| Reasoning tokens [M] | 1,240 |
| Cache read tokens [M] | 154,624 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **29,271** |
| Thinking ratio [C] | 4.2% |
| Output efficiency [C] | 22.1% |
| Input cost [C] | $0.107760 |
| Output cost [C] | $0.194370 |
| Reasoning cost [C] | $0.037200 |
| Cache cost [C] | $0.077312 |
| **Total cost** | **$0.416642** |
| **Total energy [X]** | **~3797 J** |
| Solution density [C] | 0.013324 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000159 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.4166  |  **Energy:** ~3797J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_fp4wko3z/session.jsonl)
- [Generated code](./exp_fp4wko3z/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 390 |
| Functions | 33 |
| Classes | 0 |
| Functions/file | 11.0 |
| Classes/file | 0.0 |
| Avg lines/file | 130 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 14 |
| Decorators | 12 |
| Test files | 1 |
| Test file rate | 33% |
| Parse errors | 0 |
