# Game Report: exp_x8g28_k8-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [baseline] cd_openai_GPT_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T03:08:36

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.659

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.64) with moderate resource use ($0.0180, ~2629J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.5% |
| Quality/$ | 115 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 187 |
| Cyclomatic complexity | 28.0 |
| Code quality | 0.533 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.641** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 14,349 |
| Completion tokens | 4,216 |
| Reasoning tokens | 1,088 |
| **Total tokens** | **19,653** |
| Thinking ratio | 5.5% |
| Output efficiency | 21.5% |
| Input cost | $0.003874 |
| Output cost | $0.004638 |
| Reasoning cost | $0.000152 |
| **Total cost** | **$0.018000** |
| **Total energy** | **~2629 J** |
| Solution density | 0.009515 LOC/tok |
| Correctness/$ | 81 |
| Quality/J | 0.000244 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0180  |  **Energy:** ~2629J  |  **Thinking:** 6%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 187 |
| Functions | 23 |
| Classes | 4 |
| Functions/file | 11.5 |
| Classes/file | 2.0 |
| Avg lines/file | 94 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 16 |
| Decorators | 16 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,216 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0444 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

