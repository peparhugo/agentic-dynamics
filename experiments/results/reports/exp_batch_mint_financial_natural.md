# Game Report: mint_financial-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:mint_financial:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:49:42

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.766

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.65) with moderate resource use ($0.0175, ~4502J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 4.3% |
| Quality/$ | 54 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 1530 |
| Cyclomatic complexity | 148.0 |
| Code quality | 0.065 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.652** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 7,663 |
| Completion tokens | 14,861 |
| Reasoning tokens | 1,001 |
| **Total tokens** | **23,525** |
| Thinking ratio | 4.3% |
| Output efficiency | 63.2% |
| Input cost | $0.002069 |
| Output cost | $0.016347 |
| Reasoning cost | $0.000140 |
| **Total cost** | **$0.017502** |
| **Total energy** | **~4502 J** |
| Solution density | 0.065037 LOC/tok |
| Correctness/$ | 54 |
| Quality/J | 0.000145 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0175  |  **Energy:** ~4502J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_mint_financial_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 41 |
| Total lines (Py) | 1530 |
| Functions | 18 |
| Classes | 53 |
| Functions/file | 0.4 |
| Classes/file | 1.3 |
| Avg lines/file | 37 |
| Type hints | 114% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 205 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
