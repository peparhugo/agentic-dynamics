# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [inject_alien_vocab_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:21

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.919

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.2930, ~2730J, 2% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 2.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 444 |
| Cyclomatic complexity [C] | 116.0 |
| Code quality [H] | 0.225 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.641** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 13,488 |
| Completion tokens [M] | 6,338 |
| Reasoning tokens [M] | 412 |
| Cache read tokens [M] | 46,080 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,238** |
| Thinking ratio [C] | 2.0% |
| Output efficiency [C] | 31.3% |
| Input cost [C] | $0.067440 |
| Output cost [C] | $0.190140 |
| Reasoning cost [C] | $0.012360 |
| Cache cost [C] | $0.023040 |
| **Total cost** | **$0.292980** |
| **Total energy [X]** | **~2730 J** |
| Solution density [C] | 0.021939 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000235 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.2930  |  **Energy:** ~2730J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_9iaxwdel/session.jsonl)
- [Generated code](./exp_9iaxwdel/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines (Py) | 444 |
| Functions | 35 |
| Classes | 4 |
| Functions/file | 3.9 |
| Classes/file | 0.4 |
| Avg lines/file | 49 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 38 |
| Decorators | 32 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
