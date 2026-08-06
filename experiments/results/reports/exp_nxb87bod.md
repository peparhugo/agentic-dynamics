# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_gather_gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:28:57

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.809

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.74) with moderate resource use ($0.7495, ~1912J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.289 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.133 |
| Thinking ratio [C] | 7.8% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (13/13 tests) [M] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 407 |
| Cyclomatic complexity [C] | 80.0 |
| Code quality [H] | 0.246 |
| Novelty vs baseline [H] | 0.829 |
| **Composite [H]** | **0.738** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 33 |
| Completion tokens [M] | 7,079 |
| Reasoning tokens [M] | 598 |
| Cache read tokens [M] | 100,800 |
| Cache write tokens [M] | 15,020 |
| **Total tokens** | **7,710** |
| Thinking ratio [C] | 7.8% |
| Output efficiency [C] | 91.8% |
| Input cost [M] | $0.000174 |
| Output cost [M] | $0.299147 |
| Reasoning cost [M] | $0.025271 |
| Cache cost [M] | $0.424908 |
| **Total cost** | **$0.749500** |
| **Total energy [X]** | **~1912 J** |
| Solution density [C] | 0.052789 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000386 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.7495  |  **Energy:** ~1912J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_nxb87bod/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 407 |
| Functions | 44 |
| Classes | 1 |
| Functions/file | 22.0 |
| Classes/file | 0.5 |
| Avg lines/file | 204 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 12 |
| Decorators | 23 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 13 |
| Failed | 0 |
| Errors | 0 |
| Total | 13 |
| Pass rate | 100% |
| Duration | 5.2s |
