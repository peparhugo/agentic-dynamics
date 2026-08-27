# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] process_perturbation_resample...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:06

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.896

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0097, ~2478J, 10% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 9.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 347 |
| Cyclomatic complexity [C] | 42.0 |
| Code quality [H] | 0.288 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.611** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,152 |
| Completion tokens [M] | 5,535 |
| Reasoning tokens [M] | 1,347 |
| Cache read tokens [M] | 160,000 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **14,034** |
| Thinking ratio [C] | 9.6% |
| Output efficiency [C] | 39.4% |
| Input cost [M] | $0.002089 |
| Output cost [M] | $0.004851 |
| Reasoning cost [M] | $0.001180 |
| Cache cost [M] | $0.001558 |
| **Total cost** | **$0.009678** |
| **Total energy [X]** | **~2478 J** |
| Solution density [C] | 0.024726 LOC/tok |
| Correctness/$ [C] | 46 |
| Quality/J [C] | 0.000247 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0097  |  **Energy:** ~2478J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_w3h7zigv/session.jsonl)
- [Generated code](./exp_w3h7zigv/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 347 |
| Functions | 39 |
| Classes | 3 |
| Functions/file | 19.5 |
| Classes/file | 1.5 |
| Avg lines/file | 174 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 3 |
| Imports | 12 |
| Decorators | 8 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |
