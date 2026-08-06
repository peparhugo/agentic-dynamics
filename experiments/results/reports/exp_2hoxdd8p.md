# Game Report: standardized_retry-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [standardized_retry] gpt_5_nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:40:11

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.709

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=70%). Cost: $0.0095, ~6910J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.737 |
| Architecture div | 0.833 |
| Structure div | 0.380 |
| Thinking ratio | 19.3% |
| Quality/$ | 68 |
| Quality/J | 0.0001 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 246 |
| Cyclomatic complexity | 41.0 |
| Code quality | 0.407 |
| Novelty vs baseline | 0.966 |
| **Composite** | **0.600** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 24,667 |
| Completion tokens | 6,294 |
| Reasoning tokens | 7,424 |
| **Total tokens** | **38,385** |
| Thinking ratio | 19.3% |
| Output efficiency | 16.4% |
| Input cost | $0.006660 |
| Output cost | $0.006923 |
| Reasoning cost | $0.001039 |
| **Total cost** | **$0.009503** |
| **Total energy** | **~6910 J** |
| Solution density | 0.006409 LOC/tok |
| Correctness/$ | 48 |
| Quality/J | 0.000087 |

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

