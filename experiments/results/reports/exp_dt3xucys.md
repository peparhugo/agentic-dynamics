# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [inject_phantom_success_s0.5] task_manager...
**Operator:** perturbed (specification_corruption, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:03

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.923

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.5426, ~5319J, 1% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.175 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.075 |
| Thinking ratio [C] | 1.0% |
| Quality/$ [C] | 23 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 743 |
| Cyclomatic complexity [C] | 132.0 |
| Code quality [H] | 0.135 |
| Novelty vs baseline [H] | 0.507 |
| **Composite [H]** | **0.667** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 29,527 |
| Completion tokens [M] | 12,008 |
| Reasoning tokens [M] | 414 |
| Cache read tokens [M] | 44,544 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **41,949** |
| Thinking ratio [C] | 1.0% |
| Output efficiency [C] | 28.6% |
| Input cost [C] | $0.147635 |
| Output cost [C] | $0.360240 |
| Reasoning cost [C] | $0.012420 |
| Cache cost [C] | $0.022272 |
| **Total cost** | **$0.542567** |
| **Total energy [X]** | **~5319 J** |
| Solution density [C] | 0.017712 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000125 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.5426  |  **Energy:** ~5319J  |  **Thinking:** 1%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_dt3xucys/session.jsonl)
- [Generated code](./exp_dt3xucys/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 11 |
| Total lines (Py) | 743 |
| Functions | 62 |
| Classes | 0 |
| Functions/file | 5.6 |
| Classes/file | 0.0 |
| Avg lines/file | 68 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 10 |
| Imports | 32 |
| Decorators | 32 |
| Test files | 4 |
| Test file rate | 36% |
| Parse errors | 0 |
