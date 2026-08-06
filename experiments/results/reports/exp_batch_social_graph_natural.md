# Game Report: social_graph-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:social_graph:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:49:54

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.753

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.44) with moderate resource use ($0.0130, ~3568J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 10.9% |
| Quality/$ | 84 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 98% (91/93 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 1333 |
| Cyclomatic complexity | 260.0 |
| Code quality | 0.075 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.440** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 7,775 |
| Completion tokens | 8,684 |
| Reasoning tokens | 2,019 |
| **Total tokens** | **18,478** |
| Thinking ratio | 10.9% |
| Output efficiency | 47.0% |
| Input cost | $0.002099 |
| Output cost | $0.009552 |
| Reasoning cost | $0.000283 |
| **Total cost** | **$0.013010** |
| **Total energy** | **~3568 J** |
| Solution density | 0.072140 LOC/tok |
| Correctness/$ | 84 |
| Quality/J | 0.000123 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 98%  |  **Cost:** $0.0130  |  **Energy:** ~3568J  |  **Thinking:** 11%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_social_graph_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 17 |
| Total lines (Py) | 1333 |
| Functions | 196 |
| Classes | 22 |
| Functions/file | 11.5 |
| Classes/file | 1.3 |
| Avg lines/file | 78 |
| Type hints | 73% |
| Docstrings | 0% |
| Error handlers | 1 |
| Imports | 68 |
| Decorators | 20 |
| Test files | 7 |
| Test file rate | 41% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 91 |
| Failed | 2 |
| Errors | 0 |
| Total | 93 |
| Pass rate | 98% |
| Duration | 0.7s |
