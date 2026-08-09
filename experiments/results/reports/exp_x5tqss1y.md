# Game Report: exp_x5tqss1y-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:44:55

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.697

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.42) with moderate resource use ($0.0185, ~4258J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 4.2% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 883 |
| Cyclomatic complexity [C] | 65.0 |
| Code quality [H] | 0.113 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.421** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,217 |
| Completion tokens [M] | 12,869 |
| Reasoning tokens [M] | 1,022 |
| Cache read tokens [M] | 557,312 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **24,108** |
| Thinking ratio [C] | 4.2% |
| Output efficiency [C] | 53.4% |
| Input cost [M] | $0.000538 |
| Output cost [M] | $0.002762 |
| Reasoning cost [M] | $0.000028 |
| Cache cost [M] | $0.015222 |
| **Total cost** | **$0.018550** |
| **Total energy [X]** | **~4258 J** |
| Solution density [C] | 0.036627 LOC/tok |
| Correctness/$ [C] | 8 |
| Quality/J [C] | 0.000099 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0185  |  **Energy:** ~4258J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_x5tqss1y/session.jsonl)
- [Generated code](./exp_x5tqss1y/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 25 |
| JS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1463 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
