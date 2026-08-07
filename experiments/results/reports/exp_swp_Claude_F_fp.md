# Game Report: perturbed-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [silent_sweep:perturbed:forced] Claude_Fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:25:26

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.70) with moderate resource use ($0.3609, ~690J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 3 |
| Quality/J [C] | 0.0015 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 230 |
| Cyclomatic complexity [C] | 24.0 |
| Code quality [H] | 0.535 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.703** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10 |
| Completion tokens [M] | 2,995 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 48,004 |
| Cache write tokens [M] | 13,043 |
| **Total tokens** | **3,005** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.7% |
| Input cost [M] | $0.000100 |
| Output cost [M] | $0.149750 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.211042 |
| **Total cost** | **$0.360892** |
| **Total energy [X]** | **~690 J** |
| Solution density [C] | 0.076539 LOC/tok |
| Correctness/$ [C] | 9 |
| Quality/J [C] | 0.001020 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3609  |  **Energy:** ~690J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_Claude_F_fp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 230 |
| Functions | 26 |
| Classes | 11 |
| Functions/file | 4.3 |
| Classes/file | 1.8 |
| Avg lines/file | 38 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 23 |
| Decorators | 5 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
