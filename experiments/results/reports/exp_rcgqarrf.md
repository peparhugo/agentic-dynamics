# Game Report: force_abandonment_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [force_abandonment_s0.5] process_perturbation_resample...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:05

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.908

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.3586, ~3850J, 6% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 5.8% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 414 |
| Cyclomatic complexity [C] | 52.0 |
| Code quality [H] | 0.242 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.559** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,756 |
| Completion tokens [M] | 6,125 |
| Reasoning tokens [M] | 1,661 |
| Cache read tokens [M] | 42,496 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **28,542** |
| Thinking ratio [C] | 5.8% |
| Output efficiency [C] | 21.5% |
| Input cost [C] | $0.103780 |
| Output cost [C] | $0.183750 |
| Reasoning cost [C] | $0.049830 |
| Cache cost [C] | $0.021248 |
| **Total cost** | **$0.358608** |
| **Total energy [X]** | **~3850 J** |
| Solution density [C] | 0.014505 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000145 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.3586  |  **Energy:** ~3850J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_rcgqarrf/session.jsonl)
- [Generated code](./exp_rcgqarrf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 414 |
| Functions | 29 |
| Classes | 1 |
| Functions/file | 4.1 |
| Classes/file | 0.1 |
| Avg lines/file | 59 |
| Type hints | 43% |
| Docstrings | 3% |
| Error handlers | 3 |
| Imports | 19 |
| Decorators | 10 |
| Test files | 3 |
| Test file rate | 43% |
| Parse errors | 0 |
