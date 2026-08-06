# Game Report: standardized_build-perturbed

**Model:** openai/gpt-5.6  |  **Task:** [standardized_build] gpt-5.6...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:27:13

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.797

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.62) with moderate resource use ($0.2664, ~1242J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.459 |
| Architecture div [H] | 0.400 |
| Structure div [H] | 0.263 |
| Thinking ratio [C] | 6.8% |
| Quality/$ [C] | 4 |
| Quality/J [C] | 0.0008 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (16/16 tests) [M] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 268 |
| Cyclomatic complexity [C] | 32.0 |
| Code quality [H] | 0.373 |
| Novelty vs baseline [H] | 0.735 |
| **Composite [H]** | **0.621** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 30 |
| Completion tokens [M] | 4,690 |
| Reasoning tokens [M] | 343 |
| Cache read tokens [M] | 77,401 |
| Cache write tokens [M] | 12,250 |
| **Total tokens** | **5,063** |
| Thinking ratio [C] | 6.8% |
| Output efficiency [C] | 92.6% |
| Input cost [M] | $0.000077 |
| Output cost [M] | $0.096579 |
| Reasoning cost [M] | $0.007063 |
| Cache cost [M] | $0.162683 |
| **Total cost** | **$0.266403** |
| **Total energy [X]** | **~1242 J** |
| Solution density [C] | 0.052933 LOC/tok |
| Correctness/$ [C] | 8 |
| Quality/J [C] | 0.000499 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.2664  |  **Energy:** ~1242J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_kpkjjdv3/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 268 |
| Functions | 27 |
| Classes | 1 |
| Functions/file | 13.5 |
| Classes/file | 0.5 |
| Avg lines/file | 134 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 14 |
| Decorators | 10 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 16 |
| Failed | 0 |
| Errors | 0 |
| Total | 16 |
| Pass rate | 100% |
| Duration | 1.7s |
