# Game Report: mint_financial-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:mint_financial:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:18:38

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.766

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.61) with moderate resource use ($0.0175, ~4502J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 4.3% |
| Quality/$ [C] | 57 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 1530 |
| Cyclomatic complexity [C] | 148.0 |
| Code quality [H] | 0.065 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.610** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,663 |
| Completion tokens [M] | 14,861 |
| Reasoning tokens [M] | 1,001 |
| Cache read tokens [M] | 101,632 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,525** |
| Thinking ratio [C] | 4.3% |
| Output efficiency [C] | 63.2% |
| Input cost [M] | $0.001105 |
| Output cost [M] | $0.008727 |
| Reasoning cost [M] | $0.000075 |
| Cache cost [M] | $0.007596 |
| **Total cost** | **$0.017502** |
| **Total energy [X]** | **~4502 J** |
| Solution density [C] | 0.065037 LOC/tok |
| Correctness/$ [C] | 31 |
| Quality/J [C] | 0.000135 |

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
