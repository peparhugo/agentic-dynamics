# Game Report: perturbed-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:perturbed:forced] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:52:49

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0323, ~5369J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.4% |
| Quality/$ | 31 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 281 |
| Cyclomatic complexity | 52.0 |
| Code quality | 0.356 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.753** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 36,992 |
| Completion tokens | 5,507 |
| Reasoning tokens | 2,432 |
| **Total tokens** | **44,931** |
| Thinking ratio | 5.4% |
| Output efficiency | 12.3% |
| **Total cost** | **$0.032320** |
| **Total energy** | **~5369 J** |
| Solution density | 0.006254 LOC/tok |
| Correctness/$ | 61 |
| Quality/J | 0.000140 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0323  |  **Energy:** ~5369J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_mini_fp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 281 |
| Functions | 27 |
| Classes | 5 |
| Functions/file | 3.9 |
| Classes/file | 0.7 |
| Avg lines/file | 40 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 27 |
| Decorators | 18 |
| Test files | 2 |
| Test file rate | 29% |
| Parse errors | 0 |
