# Game Report: baseline-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:baseline:forced] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:25:25

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.761

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.73) with moderate resource use ($0.3088, ~1674J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.0% |
| Quality/$ [C] | 3 |
| Quality/J [C] | 0.0006 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 427 |
| Cyclomatic complexity [C] | 85.0 |
| Code quality [H] | 0.234 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.729** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18 |
| Completion tokens [M] | 6,304 |
| Reasoning tokens [M] | 474 |
| Cache read tokens [M] | 40,859 |
| Cache write tokens [M] | 13,583 |
| **Total tokens** | **6,796** |
| Thinking ratio [C] | 7.0% |
| Output efficiency [C] | 92.8% |
| Input cost [M] | $0.000055 |
| Output cost [M] | $0.152901 |
| Reasoning cost [M] | $0.011497 |
| Cache cost [M] | $0.144301 |
| **Total cost** | **$0.308753** |
| **Total energy [X]** | **~1674 J** |
| Solution density [C] | 0.062831 LOC/tok |
| Correctness/$ [C] | 8 |
| Quality/J [C] | 0.000435 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3088  |  **Energy:** ~1674J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_6_fb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 427 |
| Functions | 43 |
| Classes | 4 |
| Functions/file | 21.5 |
| Classes/file | 2.0 |
| Avg lines/file | 214 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 13 |
| Decorators | 33 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |
