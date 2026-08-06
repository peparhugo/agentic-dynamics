# Game Report: social_graph-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:social_graph:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:21:37

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.753

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.44) with moderate resource use ($0.0130, ~3568J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 10.9% |
| Quality/$ [C] | 77 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 98% (91/93 tests) [M] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 1333 |
| Cyclomatic complexity [C] | 260.0 |
| Code quality [H] | 0.075 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.440** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,775 |
| Completion tokens [M] | 8,684 |
| Reasoning tokens [M] | 2,019 |
| Cache read tokens [M] | 87,168 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **18,478** |
| Thinking ratio [C] | 10.9% |
| Output efficiency [C] | 47.0% |
| Input cost [M] | $0.001131 |
| Output cost [M] | $0.005149 |
| Reasoning cost [M] | $0.000152 |
| Cache cost [M] | $0.006577 |
| **Total cost** | **$0.013010** |
| **Total energy [X]** | **~3568 J** |
| Solution density [C] | 0.072140 LOC/tok |
| Correctness/$ [C] | 41 |
| Quality/J [C] | 0.000123 |

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
| Duration | 0.6s |
