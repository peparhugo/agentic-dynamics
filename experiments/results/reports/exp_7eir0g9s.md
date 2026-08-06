# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [inject_phantom_success_s0.5_r2] cd_openai_GPT_5_mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:15:39

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.816

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.87) with moderate resource use ($0.0146, ~2132J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.400 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.167 |
| Thinking ratio [C] | 4.4% |
| Quality/$ [C] | 69 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 202 |
| Cyclomatic complexity [C] | 42.0 |
| Code quality [H] | 0.495 |
| Novelty vs baseline [H] | 0.834 |
| **Composite [H]** | **0.874** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 11,627 |
| Completion tokens [M] | 3,786 |
| Reasoning tokens [M] | 704 |
| Cache read tokens [M] | 106,880 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **16,117** |
| Thinking ratio [C] | 4.4% |
| Output efficiency [C] | 23.5% |
| Input cost [M] | $0.001676 |
| Output cost [M] | $0.004366 |
| Reasoning cost [M] | $0.000812 |
| Cache cost [M] | $0.007704 |
| **Total cost** | **$0.014559** |
| **Total energy [X]** | **~2132 J** |
| Solution density [C] | 0.012533 LOC/tok |
| Correctness/$ [C] | 8 |
| Quality/J [C] | 0.000410 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0146  |  **Energy:** ~2132J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_7eir0g9s/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines (Py) | 202 |
| Functions | 22 |
| Classes | 0 |
| Functions/file | 2.4 |
| Classes/file | 0.0 |
| Avg lines/file | 22 |
| Type hints | 11% |
| Docstrings | 5% |
| Error handlers | 8 |
| Imports | 26 |
| Decorators | 12 |
| Test files | 2 |
| Test file rate | 22% |
| Parse errors | 0 |
