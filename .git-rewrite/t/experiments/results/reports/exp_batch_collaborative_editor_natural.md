# Game Report: collaborative_editor-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:collaborative_editor:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:16:33

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.59) with moderate resource use ($0.0221, ~5498J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 5.6% |
| Quality/$ [C] | 45 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 50% (2/4 constraints) |
| Lines of code [M] | 1227 |
| Cyclomatic complexity [C] | 136.0 |
| Code quality [H] | 0.081 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.591** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,858 |
| Completion tokens [M] | 12,588 |
| Reasoning tokens [M] | 1,987 |
| Cache read tokens [M] | 95,360 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **35,433** |
| Thinking ratio [C] | 5.6% |
| Output efficiency [C] | 35.5% |
| Input cost [M] | $0.003759 |
| Output cost [M] | $0.009243 |
| Reasoning cost [M] | $0.000186 |
| Cache cost [M] | $0.008911 |
| **Total cost** | **$0.022099** |
| **Total energy [X]** | **~5498 J** |
| Solution density [C] | 0.034629 LOC/tok |
| Correctness/$ [C] | 30 |
| Quality/J [C] | 0.000108 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0221  |  **Energy:** ~5498J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_collaborative_editor_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 18 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1206 |
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
