# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** openai/gpt-5.6-luna  |  **Task:** [inject_alien_vocab_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:06

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.814

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.0154, ~3439J, 2% thinking). Thermodynamically optimal.

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
| Lines of code [M] | 284 |
| Cyclomatic complexity [C] | 79.0 |
| Code quality [H] | 0.352 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.390** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 19,534 |
| Completion tokens [M] | 7,079 |
| Reasoning tokens [M] | 527 |
| Cache read tokens [M] | 120,320 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,140** |
| Thinking ratio [C] | 1.9% |
| Output efficiency [C] | 26.1% |
| Input cost [C] | $0.003907 |
| Output cost [C] | $0.008495 |
| Reasoning cost [C] | $0.000632 |
| Cache cost [C] | $0.002406 |
| **Total cost** | **$0.015440** |
| **Total energy [X]** | **~3439 J** |
| Solution density [C] | 0.010464 LOC/tok |
| Correctness/$ [C] | 45 |
| Quality/J [C] | 0.000176 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.0154  |  **Energy:** ~3439J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_y8hkennr/session.jsonl)
- [Generated code](./exp_y8hkennr/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 284 |
| Functions | 30 |
| Classes | 0 |
| Functions/file | 3.8 |
| Classes/file | 0.0 |
| Avg lines/file | 36 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 24 |
| Decorators | 17 |
| Test files | 2 |
| Test file rate | 25% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,079 |
| Python files | 8 |
| Non-Python files | 0 |
| Code density | 0.0401 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

