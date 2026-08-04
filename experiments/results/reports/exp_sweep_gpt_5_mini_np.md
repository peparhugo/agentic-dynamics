# Game Report: perturbed-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:perturbed:natural] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:59

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.656

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.59) with moderate resource use ($0.0284, ~3978J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 6.8% |
| Quality/$ | 77 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 342 |
| Cyclomatic complexity | 68.0 |
| Code quality | 0.292 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.593** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18,472 |
| Completion tokens | 7,076 |
| Reasoning tokens | 1,856 |
| **Total tokens** | **27,404** |
| Thinking ratio | 6.8% |
| Output efficiency | 25.8% |
| Input cost | $0.004987 |
| Output cost | $0.007784 |
| Reasoning cost | $0.000260 |
| **Total cost** | **$0.028373** |
| **Total energy** | **~3978 J** |
| Solution density | 0.012480 LOC/tok |
| Correctness/$ | 54 |
| Quality/J | 0.000149 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0284  |  **Energy:** ~3978J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 5 |
| Total lines | 342 |
| Functions | 31 |
| Classes | 4 |
| Functions/file | 6.2 |
| Classes/file | 0.8 |
| Avg lines/file | 68 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 29 |
| Decorators | 18 |
| Test files | 2 |
| Test file rate | 40% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,076 |
| Python files | 5 |
| Non-Python files | 0 |
| Code density | 0.0483 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |


---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_mini_np/code/)
