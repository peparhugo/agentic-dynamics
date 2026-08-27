# Game Report: invert_constraint_s0.5-perturbed

**Model:** openai/gpt-5.6-luna  |  **Task:** [invert_constraint_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:48

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.823

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.0170, ~3685J, 3% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.200 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.091 |
| Thinking ratio [C] | 2.9% |
| Quality/$ [C] | 24 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 285 |
| Cyclomatic complexity [C] | 93.0 |
| Code quality [H] | 0.351 |
| Novelty vs baseline [H] | 0.576 |
| **Composite [H]** | **0.402** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,522 |
| Completion tokens [M] | 7,174 |
| Reasoning tokens [M] | 837 |
| Cache read tokens [M] | 165,376 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **28,533** |
| Thinking ratio [C] | 2.9% |
| Output efficiency [C] | 25.1% |
| Input cost [C] | $0.004104 |
| Output cost [C] | $0.008609 |
| Reasoning cost [C] | $0.001004 |
| Cache cost [C] | $0.003308 |
| **Total cost** | **$0.017025** |
| **Total energy [X]** | **~3685 J** |
| Solution density [C] | 0.009988 LOC/tok |
| Correctness/$ [C] | 41 |
| Quality/J [C] | 0.000155 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.0170  |  **Energy:** ~3685J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_knt09sid/session.jsonl)
- [Generated code](./exp_knt09sid/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 285 |
| Functions | 33 |
| Classes | 0 |
| Functions/file | 4.1 |
| Classes/file | 0.0 |
| Avg lines/file | 36 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 26 |
| Decorators | 22 |
| Test files | 2 |
| Test file rate | 25% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,174 |
| Python files | 8 |
| Non-Python files | 0 |
| Code density | 0.0397 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

