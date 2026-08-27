# Game Report: reverse_causality_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [reverse_causality_s0.5] process_perturbation_resample...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:49

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.876

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0152, ~4199J, 16% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 16.3% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 541 |
| Cyclomatic complexity [C] | 83.0 |
| Code quality [H] | 0.185 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.633** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,178 |
| Completion tokens [M] | 8,687 |
| Reasoning tokens [M] | 3,292 |
| Cache read tokens [M] | 338,048 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,157** |
| Thinking ratio [C] | 16.3% |
| Output efficiency [C] | 43.1% |
| Input cost [M] | $0.002245 |
| Output cost [M] | $0.007155 |
| Reasoning cost [M] | $0.002711 |
| Cache cost [M] | $0.003094 |
| **Total cost** | **$0.015205** |
| **Total energy [X]** | **~4199 J** |
| Solution density [C] | 0.026839 LOC/tok |
| Correctness/$ [C] | 27 |
| Quality/J [C] | 0.000151 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0152  |  **Energy:** ~4199J  |  **Thinking:** 16%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_wdek_qaf/session.jsonl)
- [Generated code](./exp_wdek_qaf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 12 |
| Total lines (Py) | 541 |
| Functions | 60 |
| Classes | 4 |
| Functions/file | 5.0 |
| Classes/file | 0.3 |
| Avg lines/file | 45 |
| Type hints | 30% |
| Docstrings | 8% |
| Error handlers | 10 |
| Imports | 35 |
| Decorators | 7 |
| Test files | 5 |
| Test file rate | 42% |
| Parse errors | 0 |
