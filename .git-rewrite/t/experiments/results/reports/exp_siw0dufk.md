# Game Report: std_final-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [std_final] gpt_5_mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:25:25

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.810

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.69) with moderate resource use ($0.0159, ~2796J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.417 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.227 |
| Thinking ratio [C] | 7.1% |
| Quality/$ [C] | 63 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 221 |
| Cyclomatic complexity [C] | 41.0 |
| Code quality [H] | 0.452 |
| Novelty vs baseline [H] | 0.831 |
| **Composite [H]** | **0.694** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 15,572 |
| Completion tokens [M] | 3,733 |
| Reasoning tokens [M] | 1,472 |
| Cache read tokens [M] | 62,848 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,777** |
| Thinking ratio [C] | 7.1% |
| Output efficiency [C] | 18.0% |
| Input cost [M] | $0.002789 |
| Output cost [M] | $0.005348 |
| Reasoning cost [M] | $0.002109 |
| Cache cost [M] | $0.005628 |
| **Total cost** | **$0.015874** |
| **Total energy [X]** | **~2796 J** |
| Solution density [C] | 0.010637 LOC/tok |
| Correctness/$ [C] | 9 |
| Quality/J [C] | 0.000248 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0159  |  **Energy:** ~2796J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_siw0dufk/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 221 |
| Functions | 18 |
| Classes | 0 |
| Functions/file | 6.0 |
| Classes/file | 0.0 |
| Avg lines/file | 74 |
| Type hints | 19% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 15 |
| Decorators | 6 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |
