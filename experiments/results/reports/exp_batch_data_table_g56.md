# Game Report: data_table-baseline

**Model:** openai/gpt-5.6  |  **Task:** [batch:data_table:baseline] gpt56_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:19:15

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.470

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=60%, quality=0.53) with moderate resource use ($0.6613, ~3529J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.4% |
| Quality/$ [C] | 2 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (8/8 tests) [M] |
| Constraint satisfaction [H] | 25% (1/4 constraints) |
| Lines of code [M] | 29 |
| Cyclomatic complexity [C] | 8.0 |
| Code quality [H] | 0.867 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.533** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 39 |
| Completion tokens [M] | 13,171 |
| Reasoning tokens [M] | 1,057 |
| Cache read tokens [M] | 193,567 |
| Cache write tokens [M] | 22,003 |
| **Total tokens** | **14,267** |
| Thinking ratio [C] | 7.4% |
| Output efficiency [C] | 92.3% |
| Input cost [M] | $0.000101 |
| Output cost [M] | $0.273643 |
| Reasoning cost [M] | $0.021960 |
| Cache cost [M] | $0.365633 |
| **Total cost** | **$0.661337** |
| **Total energy [X]** | **~3529 J** |
| Solution density [C] | 0.002033 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000151 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.6613  |  **Energy:** ~3529J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_data_table_g56/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| TS files | 4 |
| TSX files | 3 |
| JS files | 2 |
| Total lines (Py) | 29 |
| Total lines (TS/TSX) | 650 |
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

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 8 |
| Failed | 0 |
| Errors | 0 |
| Total | 8 |
| Pass rate | 100% |
| Duration | 0.4s |
