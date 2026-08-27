# Game Report: baseline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:baseline:forced] DeepSeek_v4_Pro...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:48

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.806

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.0371, ~12930J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 39.7% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 1101 |
| Cyclomatic complexity [C] | 98.0 |
| Code quality [H] | 0.091 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.700** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,939 |
| Completion tokens [M] | 16,097 |
| Reasoning tokens [M] | 17,772 |
| Cache read tokens [M] | 790,784 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **44,808** |
| Thinking ratio [C] | 39.7% |
| Output efficiency [C] | 35.9% |
| Input cost [M] | $0.002921 |
| Output cost [M] | $0.012895 |
| Reasoning cost [M] | $0.014237 |
| Cache cost [M] | $0.007039 |
| **Total cost** | **$0.037091** |
| **Total energy [X]** | **~12930 J** |
| Solution density [C] | 0.024572 LOC/tok |
| Correctness/$ [C] | 11 |
| Quality/J [C] | 0.000054 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0371  |  **Energy:** ~12930J  |  **Thinking:** 40%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_DeepSeek_fb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 22 |
| Total lines (Py) | 1101 |
| Functions | 120 |
| Classes | 12 |
| Functions/file | 5.5 |
| Classes/file | 0.5 |
| Avg lines/file | 50 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 80 |
| Decorators | 36 |
| Test files | 9 |
| Test file rate | 41% |
| Parse errors | 0 |
