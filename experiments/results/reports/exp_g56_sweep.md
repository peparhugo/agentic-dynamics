# Game Report: baseline-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:baseline:natural] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:19

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.4637, ~2582J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.9% |
| Quality/$ | 2 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 638 |
| Cyclomatic complexity | 92.0 |
| Code quality | 0.157 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.713** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 27 |
| Completion tokens | 9,541 |
| Reasoning tokens | 820 |
| **Total tokens** | **10,388** |
| Thinking ratio | 7.9% |
| Output efficiency | 91.8% |
| **Total cost** | **$0.463703** |
| **Total energy** | **~2582 J** |
| Solution density | 0.061417 LOC/tok |
| Correctness/$ | 94 |
| Quality/J | 0.000276 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.4637  |  **Energy:** ~2582J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_g56_sweep/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 638 |
| Functions | 59 |
| Classes | 7 |
| Functions/file | 5.9 |
| Classes/file | 0.7 |
| Avg lines/file | 64 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 42 |
| Decorators | 28 |
| Test files | 2 |
| Test file rate | 20% |
| Parse errors | 0 |
