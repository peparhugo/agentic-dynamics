# Game Report: exp_6ij8p3sl-baseline

**Model:** openai/gpt-5-nano  |  **Task:** [baseline] cd_gpt_5_nano...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:43:45

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.735

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.68) with moderate resource use ($0.0037, ~3083J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 14.8% |
| Quality/$ | 271 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 182 |
| Cyclomatic complexity | 31.0 |
| Code quality | 0.500 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.677** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,787 |
| Completion tokens | 4,289 |
| Reasoning tokens | 2,624 |
| **Total tokens** | **17,700** |
| Thinking ratio | 14.8% |
| Output efficiency | 24.2% |
| **Total cost** | **$0.003687** |
| **Total energy** | **~3083 J** |
| Solution density | 0.010282 LOC/tok |
| Correctness/$ | 88 |
| Quality/J | 0.000220 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0037  |  **Energy:** ~3083J  |  **Thinking:** 15%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_6ij8p3sl/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 182 |
| Functions | 22 |
| Classes | 1 |
| Functions/file | 11.0 |
| Classes/file | 0.5 |
| Avg lines/file | 91 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 10 |
| Decorators | 13 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,289 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0424 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

