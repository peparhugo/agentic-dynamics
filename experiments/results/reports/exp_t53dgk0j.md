# Game Report: invert_constraint_s0.5-perturbed

**Model:** openai/gpt-5.6-terra  |  **Task:** [invert_constraint_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.814

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.1854, ~3276J, 2% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 1.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 317 |
| Cyclomatic complexity [C] | 91.0 |
| Code quality [H] | 0.315 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.383** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 17,968 |
| Completion tokens [M] | 7,026 |
| Reasoning tokens [M] | 473 |
| Cache read tokens [M] | 112,128 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **25,467** |
| Thinking ratio [C] | 1.9% |
| Output efficiency [C] | 27.6% |
| Input cost [C] | $0.044920 |
| Output cost [C] | $0.105390 |
| Reasoning cost [C] | $0.007095 |
| Cache cost [C] | $0.028032 |
| **Total cost** | **$0.185437** |
| **Total energy [X]** | **~3276 J** |
| Solution density [C] | 0.012447 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000169 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.1854  |  **Energy:** ~3276J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_t53dgk0j/session.jsonl)
- [Generated code](./exp_t53dgk0j/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 317 |
| Functions | 39 |
| Classes | 0 |
| Functions/file | 13.0 |
| Classes/file | 0.0 |
| Avg lines/file | 106 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 10 |
| Decorators | 21 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,026 |
| Python files | 3 |
| Non-Python files | 0 |
| Code density | 0.0451 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

