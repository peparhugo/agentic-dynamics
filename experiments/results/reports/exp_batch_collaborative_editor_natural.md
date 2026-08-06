# Game Report: collaborative_editor-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:collaborative_editor:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:47:19

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.59) with moderate resource use ($0.0221, ~5498J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.6% |
| Quality/$ | 51 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 50% (2/4 constraints) |
| Lines of code | 1227 |
| Cyclomatic complexity | 136.0 |
| Code quality | 0.081 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.591** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 20,858 |
| Completion tokens | 12,588 |
| Reasoning tokens | 1,987 |
| **Total tokens** | **35,433** |
| Thinking ratio | 5.6% |
| Output efficiency | 35.5% |
| Input cost | $0.005632 |
| Output cost | $0.013847 |
| Reasoning cost | $0.000278 |
| **Total cost** | **$0.022099** |
| **Total energy** | **~5498 J** |
| Solution density | 0.034629 LOC/tok |
| Correctness/$ | 51 |
| Quality/J | 0.000108 |

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
