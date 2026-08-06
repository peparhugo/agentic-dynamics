# Game Report: collaborative_editor-baseline

**Model:** openai/gpt-5.6  |  **Task:** [batch:collaborative_editor:baseline] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:46:40

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.762

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.84) with moderate resource use ($0.7001, ~3717J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 6.6% |
| Quality/$ | 64 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (5/5 tests) |
| Constraint satisfaction | 75% (3/4 constraints) |
| Lines of code | 40 |
| Cyclomatic complexity | 4.0 |
| Code quality | 0.933 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.837** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 39 |
| Completion tokens | 14,117 |
| Reasoning tokens | 994 |
| **Total tokens** | **15,150** |
| Thinking ratio | 6.6% |
| Output efficiency | 93.2% |
| Input cost | $0.000011 |
| Output cost | $0.015529 |
| Reasoning cost | $0.000139 |
| **Total cost** | **$0.700061** |
| **Total energy** | **~3717 J** |
| Solution density | 0.002640 LOC/tok |
| Correctness/$ | 64 |
| Quality/J | 0.000225 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.7001  |  **Energy:** ~3717J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_batch_collaborative_editor_baseline gpt_/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| TS files | 8 |
| TSX files | 6 |
| JS files | 1 |
| Total lines (Py) | 40 |
| Total lines (TS/TSX) | 630 |
| Functions | 6 |
| Classes | 0 |
| Functions/file | 6.0 |
| Classes/file | 0.0 |
| Avg lines/file | 40 |
| Type hints | 17% |
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
| Passed | 5 |
| Failed | 0 |
| Errors | 0 |
| Total | 5 |
| Pass rate | 100% |
| Duration | 0.5s |
