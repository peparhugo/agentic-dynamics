# Game Report: form_wizard-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:form_wizard:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:46:59

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.690

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.40) with moderate resource use ($0.0203, ~5303J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.3% |
| Quality/$ | 49 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 405 |
| Cyclomatic complexity | 61.0 |
| Code quality | 0.247 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.404** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 14,486 |
| Completion tokens | 13,494 |
| Reasoning tokens | 2,213 |
| **Total tokens** | **30,193** |
| Thinking ratio | 7.3% |
| Output efficiency | 44.7% |
| **Total cost** | **$0.020319** |
| **Total energy** | **~5303 J** |
| Solution density | 0.013414 LOC/tok |
| Correctness/$ | 42 |
| Quality/J | 0.000076 |

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
