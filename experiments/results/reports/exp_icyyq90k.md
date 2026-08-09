# Game Report: std_final-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [std_final] deepseek...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:34:27

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.791

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.72) with moderate resource use ($0.0149, ~3590J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.368 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.200 |
| Thinking ratio [C] | 6.6% |
| Quality/$ [C] | 67 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 415 |
| Cyclomatic complexity [C] | 40.0 |
| Code quality [H] | 0.241 |
| Novelty vs baseline [H] | 0.694 |
| **Composite [H]** | **0.717** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 15,452 |
| Completion tokens [M] | 6,979 |
| Reasoning tokens [M] | 1,592 |
| Cache read tokens [M] | 207,360 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **24,023** |
| Thinking ratio [C] | 6.6% |
| Output efficiency [C] | 29.1% |
| Input cost [M] | $0.001515 |
| Output cost [M] | $0.002789 |
| Reasoning cost [M] | $0.000081 |
| Cache cost [M] | $0.010545 |
| **Total cost** | **$0.014930** |
| **Total energy [X]** | **~3590 J** |
| Solution density [C] | 0.017275 LOC/tok |
| Correctness/$ [C] | 24 |
| Quality/J [C] | 0.000200 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0149  |  **Energy:** ~3590J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_icyyq90k/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 415 |
| Functions | 8 |
| Classes | 12 |
| Functions/file | 1.0 |
| Classes/file | 1.5 |
| Avg lines/file | 52 |
| Type hints | 19% |
| Docstrings | 12% |
| Error handlers | 8 |
| Imports | 28 |
| Decorators | 2 |
| Test files | 1 |
| Test file rate | 12% |
| Parse errors | 0 |
