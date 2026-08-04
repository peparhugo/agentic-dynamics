# Game Report: data_table-baseline

**Model:** openai/gpt-5.6  |  **Task:** [batch:data_table:baseline] gpt56_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:49:23

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.470

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=60%, quality=0.53) with moderate resource use ($0.6613, ~3529J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.4% |
| Quality/$ | 68 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 60% (0/0 tests) |
| Constraint satisfaction | 25% (1/4 constraints) |
| Lines of code | 29 |
| Cyclomatic complexity | 8.0 |
| Code quality | 0.867 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.533** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 39 |
| Completion tokens | 13,171 |
| Reasoning tokens | 1,057 |
| **Total tokens** | **14,267** |
| Thinking ratio | 7.4% |
| Output efficiency | 92.3% |
| Input cost | $0.000011 |
| Output cost | $0.014488 |
| Reasoning cost | $0.000148 |
| **Total cost** | **$0.661337** |
| **Total energy** | **~3529 J** |
| Solution density | 0.002033 LOC/tok |
| Correctness/$ | 41 |
| Quality/J | 0.000151 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 60%  |  **Cost:** $0.6613  |  **Energy:** ~3529J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| Total lines | 29 |
| Functions | 8 |
| Classes | 0 |
| Functions/file | 8.0 |
| Classes/file | 0.0 |
| Avg lines/file | 29 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 1 |
| Decorators | 0 |
| Test files | 1 |
| Test file rate | 100% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_data_table_g56/code/)
