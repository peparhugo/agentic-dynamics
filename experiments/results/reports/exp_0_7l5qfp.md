# Game Report: shift_framing_s0.5-perturbed

**Model:** openai/gpt-5.6-luna  |  **Task:** [shift_framing_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:41

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.816

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.0237, ~6546J, 1% thinking). Thermodynamically optimal.

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
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 302 |
| Cyclomatic complexity [C] | 93.0 |
| Code quality [H] | 0.331 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.386** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 56,173 |
| Completion tokens [M] | 7,338 |
| Reasoning tokens [M] | 775 |
| Cache read tokens [M] | 138,240 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **64,286** |
| Thinking ratio [C] | 1.2% |
| Output efficiency [C] | 11.4% |
| Input cost [C] | $0.011235 |
| Output cost [C] | $0.008806 |
| Reasoning cost [C] | $0.000930 |
| Cache cost [C] | $0.002765 |
| **Total cost** | **$0.023735** |
| **Total energy [X]** | **~6546 J** |
| Solution density [C] | 0.004698 LOC/tok |
| Correctness/$ [C] | 29 |
| Quality/J [C] | 0.000079 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.0237  |  **Energy:** ~6546J  |  **Thinking:** 1%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_0_7l5qfp/session.jsonl)
- [Generated code](./exp_0_7l5qfp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 5 |
| Total lines (Py) | 302 |
| Functions | 32 |
| Classes | 0 |
| Functions/file | 6.4 |
| Classes/file | 0.0 |
| Avg lines/file | 60 |
| Type hints | 0% |
| Docstrings | 3% |
| Error handlers | 6 |
| Imports | 14 |
| Decorators | 15 |
| Test files | 2 |
| Test file rate | 40% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,338 |
| Python files | 5 |
| Non-Python files | 0 |
| Code density | 0.0412 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

