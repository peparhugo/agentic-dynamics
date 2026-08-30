# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** openai/gpt-5.6-luna  |  **Task:** [inject_phantom_success_s0.5] task_manager...
**Operator:** perturbed (specification_corruption, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:29

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.816

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.0185, ~4318J, 3% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.173 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.050 |
| Thinking ratio [C] | 2.6% |
| Quality/$ [C] | 20 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 324 |
| Cyclomatic complexity [C] | 72.0 |
| Code quality [H] | 0.309 |
| Novelty vs baseline [H] | 0.527 |
| **Composite [H]** | **0.386** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 26,574 |
| Completion tokens [M] | 7,636 |
| Reasoning tokens [M] | 927 |
| Cache read tokens [M] | 143,360 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **35,137** |
| Thinking ratio [C] | 2.6% |
| Output efficiency [C] | 21.7% |
| Input cost [C] | $0.005315 |
| Output cost [C] | $0.009163 |
| Reasoning cost [C] | $0.001112 |
| Cache cost [C] | $0.002867 |
| **Total cost** | **$0.018458** |
| **Total energy [X]** | **~4318 J** |
| Solution density [C] | 0.009221 LOC/tok |
| Correctness/$ [C] | 38 |
| Quality/J [C] | 0.000149 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.0185  |  **Energy:** ~4318J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_yxs6s0ee/session.jsonl)
- [Generated code](./exp_yxs6s0ee/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 324 |
| Functions | 39 |
| Classes | 0 |
| Functions/file | 5.6 |
| Classes/file | 0.0 |
| Avg lines/file | 46 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 20 |
| Decorators | 17 |
| Test files | 3 |
| Test file rate | 43% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,636 |
| Python files | 7 |
| Non-Python files | 0 |
| Code density | 0.0424 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

