# Game Report: standardized_build-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [standardized_build] gpt-5-mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:54:06

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.714

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.56) and found a novel correct solution (novelty=0.90, correctness=70%). Cost: $0.0239, ~3597J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.561 |
| Architecture div | 0.600 |
| Structure div | 0.167 |
| Thinking ratio | 8.0% |
| Quality/$ | 95 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 200 |
| Cyclomatic complexity | 24.0 |
| Code quality | 0.600 |
| Novelty vs baseline | 0.903 |
| **Composite** | **0.672** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 19,812 |
| Completion tokens | 4,432 |
| Reasoning tokens | 2,112 |
| **Total tokens** | **26,356** |
| Thinking ratio | 8.0% |
| Output efficiency | 16.8% |
| Input cost | $0.005349 |
| Output cost | $0.004875 |
| Reasoning cost | $0.000296 |
| **Total cost** | **$0.023859** |
| **Total energy** | **~3597 J** |
| Solution density | 0.007588 LOC/tok |
| Correctness/$ | 67 |
| Quality/J | 0.000187 |

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

