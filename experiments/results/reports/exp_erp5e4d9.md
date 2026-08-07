# Game Report: standardized_build-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [standardized_build] gpt-5-mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:20:09

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.714

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.56) and found a novel correct solution (novelty=0.90, correctness=70%). Cost: $0.0239, ~3597J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.561 |
| Architecture div [H] | 0.600 |
| Structure div [H] | 0.167 |
| Thinking ratio [C] | 8.0% |
| Quality/$ [C] | 42 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 200 |
| Cyclomatic complexity [C] | 24.0 |
| Code quality [H] | 0.600 |
| Novelty vs baseline [H] | 0.903 |
| **Composite [H]** | **0.629** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 19,812 |
| Completion tokens [M] | 4,432 |
| Reasoning tokens [M] | 2,112 |
| Cache read tokens [M] | 232,704 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **26,356** |
| Thinking ratio [C] | 8.0% |
| Output efficiency [C] | 16.8% |
| Input cost [M] | $0.002507 |
| Output cost [M] | $0.004487 |
| Reasoning cost [M] | $0.002138 |
| Cache cost [M] | $0.014726 |
| **Total cost** | **$0.023859** |
| **Total energy [X]** | **~3597 J** |
| Solution density [C] | 0.007588 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000175 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 70%  |  **Cost:** $0.0239  |  **Energy:** ~3597J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_erp5e4d9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 200 |
| Functions | 15 |
| Classes | 7 |
| Functions/file | 2.1 |
| Classes/file | 1.0 |
| Avg lines/file | 29 |
| Type hints | 53% |
| Docstrings | 0% |
| Error handlers | 3 |
| Imports | 28 |
| Decorators | 4 |
| Test files | 1 |
| Test file rate | 14% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,432 |
| Python files | 7 |
| Non-Python files | 0 |
| Code density | 0.0451 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

