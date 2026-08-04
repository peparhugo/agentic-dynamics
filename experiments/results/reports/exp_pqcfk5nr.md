# Game Report: exp_pqcfk5nr-baseline

**Model:** openai/gpt-5  |  **Task:** [baseline] cd_openai_GPT_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:55:48

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.644

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.60) with moderate resource use ($0.1773, ~4864J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 13.0% |
| Quality/$ | 75 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 327 |
| Cyclomatic complexity | 52.0 |
| Code quality | 0.306 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.595** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18,222 |
| Completion tokens | 7,093 |
| Reasoning tokens | 3,776 |
| **Total tokens** | **29,091** |
| Thinking ratio | 13.0% |
| Output efficiency | 24.4% |
| Input cost | $0.004920 |
| Output cost | $0.007802 |
| Reasoning cost | $0.000529 |
| **Total cost** | **$0.177260** |
| **Total energy** | **~4864 J** |
| Solution density | 0.011241 LOC/tok |
| Correctness/$ | 53 |
| Quality/J | 0.000122 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.1773  |  **Energy:** ~4864J  |  **Thinking:** 13%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines | 327 |
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

