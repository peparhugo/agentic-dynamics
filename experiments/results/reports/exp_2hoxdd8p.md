# Game Report: standardized_retry-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [standardized_retry] gpt_5_nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:18:45

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.709

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=70%). Cost: $0.0095, ~6910J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.737 |
| Architecture div [H] | 0.833 |
| Structure div [H] | 0.380 |
| Thinking ratio [C] | 19.3% |
| Quality/$ [C] | 105 |
| Quality/J [C] | 0.0001 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 246 |
| Cyclomatic complexity [C] | 41.0 |
| Code quality [H] | 0.407 |
| Novelty vs baseline [H] | 0.966 |
| **Composite [H]** | **0.600** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 24,667 |
| Completion tokens [M] | 6,294 |
| Reasoning tokens [M] | 7,424 |
| Cache read tokens [M] | 556,416 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **38,385** |
| Thinking ratio [C] | 19.3% |
| Output efficiency [C] | 16.4% |
| Input cost [M] | $0.000568 |
| Output cost [M] | $0.001160 |
| Reasoning cost [M] | $0.001368 |
| Cache cost [M] | $0.006407 |
| **Total cost** | **$0.009503** |
| **Total energy [X]** | **~6910 J** |
| Solution density [C] | 0.006409 LOC/tok |
| Correctness/$ [C] | 1 |
| Quality/J [C] | 0.000087 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 70%  |  **Cost:** $0.0095  |  **Energy:** ~6910J  |  **Thinking:** 19%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_2hoxdd8p/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 246 |
| Functions | 23 |
| Classes | 2 |
| Functions/file | 3.8 |
| Classes/file | 0.3 |
| Avg lines/file | 41 |
| Type hints | 63% |
| Docstrings | 0% |
| Error handlers | 1 |
| Imports | 31 |
| Decorators | 7 |
| Test files | 2 |
| Test file rate | 33% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 6,294 |
| Python files | 6 |
| Non-Python files | 0 |
| Code density | 0.0391 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

