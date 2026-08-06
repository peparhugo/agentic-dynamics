# Game Report: standardized_retry-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [standardized_retry] deepseek_(retry)...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:37:51

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.801

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0138, ~3031J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.316 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.338 |
| Thinking ratio [C] | 3.3% |
| Quality/$ [C] | 72 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 314 |
| Cyclomatic complexity [C] | 24.0 |
| Code quality [H] | 0.418 |
| Novelty vs baseline [H] | 0.716 |
| **Composite [H]** | **0.713** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18,390 |
| Completion tokens [M] | 5,161 |
| Reasoning tokens [M] | 794 |
| Cache read tokens [M] | 175,232 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **24,345** |
| Thinking ratio [C] | 3.3% |
| Output efficiency [C] | 21.2% |
| Input cost [M] | $0.001944 |
| Output cost [M] | $0.002223 |
| Reasoning cost [M] | $0.000044 |
| Cache cost [M] | $0.009605 |
| **Total cost** | **$0.013816** |
| **Total energy [X]** | **~3031 J** |
| Solution density [C] | 0.012898 LOC/tok |
| Correctness/$ [C] | 28 |
| Quality/J [C] | 0.000235 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0138  |  **Energy:** ~3031J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_zjb30bfm/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 314 |
| Functions | 34 |
| Classes | 3 |
| Functions/file | 4.9 |
| Classes/file | 0.4 |
| Avg lines/file | 45 |
| Type hints | 46% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 24 |
| Decorators | 9 |
| Test files | 1 |
| Test file rate | 14% |
| Parse errors | 0 |
