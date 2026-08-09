# Game Report: baseline-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [silent_sweep:baseline:forced] Claude_Fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:40:56

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.1629, ~82J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 48 |
| Cyclomatic complexity [C] | 2.0 |
| Code quality [H] | 0.967 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.704** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 2 |
| Completion tokens [M] | 356 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 0 |
| Cache write tokens [M] | 11,610 |
| **Total tokens** | **358** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.4% |
| Input cost [M] | $0.000020 |
| Output cost [M] | $0.017800 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.145125 |
| **Total cost** | **$0.162945** |
| **Total energy [X]** | **~82 J** |
| Solution density [C] | 0.134078 LOC/tok |
| Correctness/$ [C] | 20 |
| Quality/J [C] | 0.008582 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.1629  |  **Energy:** ~82J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_Claude_F_fb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| Total lines (Py) | 48 |
| Functions | 6 |
| Classes | 0 |
| Functions/file | 6.0 |
| Classes/file | 0.0 |
| Avg lines/file | 48 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 9 |
| Decorators | 5 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
