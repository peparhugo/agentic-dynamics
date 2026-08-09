# Game Report: exp_pqcfk5nr-baseline

**Model:** openai/gpt-5  |  **Task:** [baseline] cd_openai_GPT_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:38:08

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.644

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.68) with moderate resource use ($0.1773, ~4864J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 13.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 327 |
| Cyclomatic complexity [C] | 52.0 |
| Code quality [H] | 0.306 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.681** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18,222 |
| Completion tokens [M] | 7,093 |
| Reasoning tokens [M] | 3,776 |
| Cache read tokens [M] | 366,336 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **29,091** |
| Thinking ratio [C] | 13.0% |
| Output efficiency [C] | 24.4% |
| Input cost [M] | $0.011202 |
| Output cost [M] | $0.034884 |
| Reasoning cost [M] | $0.018570 |
| Cache cost [M] | $0.112603 |
| **Total cost** | **$0.177260** |
| **Total energy [X]** | **~4864 J** |
| Solution density [C] | 0.011241 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000140 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.1773  |  **Energy:** ~4864J  |  **Thinking:** 13%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_pqcfk5nr/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 327 |
| Functions | 30 |
| Classes | 8 |
| Functions/file | 3.0 |
| Classes/file | 0.8 |
| Avg lines/file | 33 |
| Type hints | 38% |
| Docstrings | 7% |
| Error handlers | 8 |
| Imports | 44 |
| Decorators | 26 |
| Test files | 2 |
| Test file rate | 20% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,093 |
| Python files | 10 |
| Non-Python files | 0 |
| Code density | 0.0461 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

