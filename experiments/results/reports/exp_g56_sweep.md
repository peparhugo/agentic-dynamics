# Game Report: baseline-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:baseline:natural] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:32:43

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.4637, ~2582J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 7.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 638 |
| Cyclomatic complexity [C] | 92.0 |
| Code quality [H] | 0.157 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.713** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 27 |
| Completion tokens [M] | 9,541 |
| Reasoning tokens [M] | 820 |
| Cache read tokens [M] | 85,525 |
| Cache write tokens [M] | 17,596 |
| **Total tokens** | **10,388** |
| Thinking ratio [C] | 7.9% |
| Output efficiency [C] | 91.8% |
| Input cost [M] | $0.000078 |
| Output cost [M] | $0.220014 |
| Reasoning cost [M] | $0.018909 |
| Cache cost [M] | $0.224702 |
| **Total cost** | **$0.463703** |
| **Total energy [X]** | **~2582 J** |
| Solution density [C] | 0.061417 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000276 |

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
