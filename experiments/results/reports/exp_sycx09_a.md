# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** openai/gpt-5.6-terra  |  **Task:** [inject_alien_vocab_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:48

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.815

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.2070, ~3788J, 2% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 1.5% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 348 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.287 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.377** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 23,802 |
| Completion tokens [M] | 7,217 |
| Reasoning tokens [M] | 477 |
| Cache read tokens [M] | 128,512 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **31,496** |
| Thinking ratio [C] | 1.5% |
| Output efficiency [C] | 22.9% |
| Input cost [C] | $0.059505 |
| Output cost [C] | $0.108255 |
| Reasoning cost [C] | $0.007155 |
| Cache cost [C] | $0.032128 |
| **Total cost** | **$0.207043** |
| **Total energy [X]** | **~3788 J** |
| Solution density [C] | 0.011049 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000156 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.2070  |  **Energy:** ~3788J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_sycx09_a/session.jsonl)
- [Generated code](./exp_sycx09_a/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 348 |
| Functions | 40 |
| Classes | 0 |
| Functions/file | 5.0 |
| Classes/file | 0.0 |
| Avg lines/file | 44 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 25 |
| Decorators | 16 |
| Test files | 3 |
| Test file rate | 38% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,217 |
| Python files | 8 |
| Non-Python files | 0 |
| Code density | 0.0482 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

