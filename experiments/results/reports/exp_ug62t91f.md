# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] process_perturbation_resample...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:09

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.697

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.43) with moderate resource use ($0.0168, ~6084J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 40.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 173 |
| Cyclomatic complexity [C] | 27.0 |
| Code quality [H] | 0.550 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.430** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,128 |
| Completion tokens [M] | 3,567 |
| Reasoning tokens [M] | 9,475 |
| Cache read tokens [M] | 279,936 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,170** |
| Thinking ratio [C] | 40.9% |
| Output efficiency [C] | 15.4% |
| Input cost [M] | $0.004406 |
| Output cost [M] | $0.003103 |
| Reasoning cost [M] | $0.008243 |
| Cache cost [M] | $0.001015 |
| **Total cost** | **$0.016767** |
| **Total energy [X]** | **~6084 J** |
| Solution density [C] | 0.007467 LOC/tok |
| Correctness/$ [C] | 42 |
| Quality/J [C] | 0.000078 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0168  |  **Energy:** ~6084J  |  **Thinking:** 41%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ug62t91f/session.jsonl)
- [Generated code](./exp_ug62t91f/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 173 |
| Functions | 12 |
| Classes | 2 |
| Functions/file | 3.0 |
| Classes/file | 0.5 |
| Avg lines/file | 43 |
| Type hints | 0% |
| Docstrings | 8% |
| Error handlers | 1 |
| Imports | 15 |
| Decorators | 9 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 3,567 |
| Python files | 4 |
| Non-Python files | 0 |
| Code density | 0.0485 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

