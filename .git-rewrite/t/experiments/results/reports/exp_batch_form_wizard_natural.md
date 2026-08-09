# Game Report: form_wizard-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:form_wizard:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:18:37

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.690

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.45) with moderate resource use ($0.0203, ~5303J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.3% |
| Quality/$ [C] | 49 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 405 |
| Cyclomatic complexity [C] | 61.0 |
| Code quality [H] | 0.247 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.447** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 14,486 |
| Completion tokens [M] | 13,494 |
| Reasoning tokens [M] | 2,213 |
| Cache read tokens [M] | 97,152 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **30,193** |
| Thinking ratio [C] | 7.3% |
| Output efficiency [C] | 44.7% |
| Input cost [M] | $0.002433 |
| Output cost [M] | $0.009233 |
| Reasoning cost [M] | $0.000193 |
| Cache cost [M] | $0.008460 |
| **Total cost** | **$0.020319** |
| **Total energy [X]** | **~5303 J** |
| Solution density [C] | 0.013414 LOC/tok |
| Correctness/$ [C] | 24 |
| Quality/J [C] | 0.000084 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0203  |  **Energy:** ~5303J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_form_wizard_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 6 |
| TSX files | 14 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1806 |
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
