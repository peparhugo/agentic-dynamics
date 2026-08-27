# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** openai/gpt-5.6-terra  |  **Task:** [inject_phantom_success_s0.5] task_manager...
**Operator:** perturbed (specification_corruption, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:48

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.817

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.1802, ~3251J, 3% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.190 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.100 |
| Thinking ratio [C] | 2.6% |
| Quality/$ [C] | 27 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 305 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.328 |
| Novelty vs baseline [H] | 0.535 |
| **Composite [H]** | **0.391** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18,189 |
| Completion tokens [M] | 6,452 |
| Reasoning tokens [M] | 663 |
| Cache read tokens [M] | 112,128 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **25,304** |
| Thinking ratio [C] | 2.6% |
| Output efficiency [C] | 25.5% |
| Input cost [C] | $0.045472 |
| Output cost [C] | $0.096780 |
| Reasoning cost [C] | $0.009945 |
| Cache cost [C] | $0.028032 |
| **Total cost** | **$0.180230** |
| **Total energy [X]** | **~3251 J** |
| Solution density [C] | 0.012053 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000199 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.1802  |  **Energy:** ~3251J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_qqo8owz4/session.jsonl)
- [Generated code](./exp_qqo8owz4/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines (Py) | 305 |
| Functions | 31 |
| Classes | 0 |
| Functions/file | 3.4 |
| Classes/file | 0.0 |
| Avg lines/file | 34 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 23 |
| Decorators | 15 |
| Test files | 3 |
| Test file rate | 33% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 6,452 |
| Python files | 9 |
| Non-Python files | 0 |
| Code density | 0.0473 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

