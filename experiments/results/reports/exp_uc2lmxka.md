# Game Report: exp_uc2lmxka-baseline

**Model:** openai/gpt-5.6  |  **Task:** [baseline] frontier_gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:53:21

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.73) with moderate resource use ($0.4089, ~2002J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.3% |
| Quality/$ | 2 |
| Quality/J | 0.0005 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 455 |
| Cyclomatic complexity | 72.0 |
| Code quality | 0.220 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.726** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 39 |
| Completion tokens | 7,797 |
| Reasoning tokens | 437 |
| **Total tokens** | **8,273** |
| Thinking ratio | 5.3% |
| Output efficiency | 94.2% |
| **Total cost** | **$0.408944** |
| **Total energy** | **~2002 J** |
| Solution density | 0.054998 LOC/tok |
| Correctness/$ | 116 |
| Quality/J | 0.000363 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.4089  |  **Energy:** ~2002J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_uc2lmxka/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 455 |
| Functions | 45 |
| Classes | 2 |
| Functions/file | 15.0 |
| Classes/file | 0.7 |
| Avg lines/file | 152 |
| Type hints | 50% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 19 |
| Decorators | 20 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |
