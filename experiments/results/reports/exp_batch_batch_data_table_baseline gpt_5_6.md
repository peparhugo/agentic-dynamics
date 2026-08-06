# Game Report: data_table-baseline

**Model:** openai/gpt-5.6  |  **Task:** [batch:data_table:baseline] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:18:39

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.691

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.61) with moderate resource use ($0.7978, ~4255J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.2% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (6/6 tests) [M] |
| Constraint satisfaction [H] | 25% (1/4 constraints) |
| Lines of code [M] | 52 |
| Cyclomatic complexity [C] | 7.0 |
| Code quality [H] | 0.883 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.607** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 45 |
| Completion tokens [M] | 15,959 |
| Reasoning tokens [M] | 1,235 |
| Cache read tokens [M] | 249,401 |
| Cache write tokens [M] | 25,125 |
| **Total tokens** | **17,239** |
| Thinking ratio [C] | 7.2% |
| Output efficiency [C] | 92.6% |
| Input cost [M] | $0.000115 |
| Output cost [M] | $0.325882 |
| Reasoning cost [M] | $0.025219 |
| Cache cost [M] | $0.446561 |
| **Total cost** | **$0.797777** |
| **Total energy [X]** | **~4255 J** |
| Solution density [C] | 0.003016 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000143 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.7978  |  **Energy:** ~4255J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_batch_data_table_baseline gpt_5_6/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| TS files | 6 |
| TSX files | 4 |
| JS files | 2 |
| Total lines (Py) | 52 |
| Total lines (TS/TSX) | 544 |
| Functions | 7 |
| Classes | 0 |
| Functions/file | 7.0 |
| Classes/file | 0.0 |
| Avg lines/file | 52 |
| Type hints | 14% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 2 |
| Decorators | 0 |
| Test files | 1 |
| Test file rate | 100% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 6 |
| Failed | 0 |
| Errors | 0 |
| Total | 6 |
| Pass rate | 100% |
| Duration | 3.5s |
