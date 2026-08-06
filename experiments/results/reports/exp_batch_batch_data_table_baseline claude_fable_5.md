# Game Report: data_table-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [batch:data_table:baseline] claude_fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:45:28

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.56) with moderate resource use ($2.0531, ~5398J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 0 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 25% (1/4 constraints) |
| Lines of code | 313 |
| Cyclomatic complexity | 111.0 |
| Code quality | 0.319 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.564** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 42 |
| Completion tokens | 23,456 |
| Reasoning tokens | 0 |
| **Total tokens** | **23,498** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| **Total cost** | **$2.053133** |
| **Total energy** | **~5398 J** |
| Solution density | 0.013320 LOC/tok |
| Correctness/$ | 39 |
| Quality/J | 0.000104 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $2.0531  |  **Energy:** ~5398J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_batch_data_table_baseline claude_fable_5/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| TS files | 10 |
| TSX files | 1 |
| Total lines (Py) | 313 |
| Total lines (TS/TSX) | 838 |
| Functions | 22 |
| Classes | 6 |
| Functions/file | 3.1 |
| Classes/file | 0.9 |
| Avg lines/file | 45 |
| Type hints | 173% |
| Docstrings | 50% |
| Error handlers | 1 |
| Imports | 19 |
| Decorators | 1 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
