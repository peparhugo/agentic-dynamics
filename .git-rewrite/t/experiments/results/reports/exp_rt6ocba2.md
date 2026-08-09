# Game Report: exp_rt6ocba2-baseline

**Model:** openai/gpt-5  |  **Task:** [baseline] quality_gpt_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:25:22

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.757

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.60) with moderate resource use ($0.1924, ~7739J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 9.1% |
| Quality/$ [C] | 5 |
| Quality/J [C] | 0.0001 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 397 |
| Cyclomatic complexity [C] | 75.0 |
| Code quality [H] | 0.252 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.604** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 46,421 |
| Completion tokens [M] | 6,646 |
| Reasoning tokens [M] | 5,312 |
| Cache read tokens [M] | 118,656 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **58,379** |
| Thinking ratio [C] | 9.1% |
| Output efficiency [C] | 11.4% |
| Input cost [M] | $0.044353 |
| Output cost [M] | $0.050799 |
| Reasoning cost [M] | $0.040602 |
| Cache cost [M] | $0.056684 |
| **Total cost** | **$0.192438** |
| **Total energy [X]** | **~7739 J** |
| Solution density [C] | 0.006800 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000078 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.1924  |  **Energy:** ~7739J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_rt6ocba2/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 397 |
| Functions | 29 |
| Classes | 4 |
| Functions/file | 14.5 |
| Classes/file | 2.0 |
| Avg lines/file | 198 |
| Type hints | 62% |
| Docstrings | 3% |
| Error handlers | 9 |
| Imports | 22 |
| Decorators | 1 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |
