# Game Report: exp_0s36_d3n-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:12:47

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.682

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.46) with moderate resource use ($0.0241, ~6074J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 11.3% |
| Quality/$ [C] | 41 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 1008 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.099 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.461** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,565 |
| Completion tokens [M] | 14,883 |
| Reasoning tokens [M] | 3,501 |
| Cache read tokens [M] | 739,072 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **30,949** |
| Thinking ratio [C] | 11.3% |
| Output efficiency [C] | 48.1% |
| Input cost [M] | $0.000662 |
| Output cost [M] | $0.003194 |
| Reasoning cost [M] | $0.000096 |
| Cache cost [M] | $0.020187 |
| **Total cost** | **$0.024139** |
| **Total energy [X]** | **~6074 J** |
| Solution density [C] | 0.032570 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000076 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0241  |  **Energy:** ~6074J  |  **Thinking:** 11%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_0s36_d3n/session.jsonl)
- [Generated code](./exp_0s36_d3n/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 21 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1578 |
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
