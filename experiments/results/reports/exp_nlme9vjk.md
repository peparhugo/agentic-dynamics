# Game Report: exp_nlme9vjk-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:23:34

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.681

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.48) with moderate resource use ($0.0126, ~3342J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 12.0% |
| Quality/$ [C] | 79 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 472 |
| Cyclomatic complexity [C] | 81.0 |
| Code quality [H] | 0.212 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.483** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,206 |
| Completion tokens [M] | 6,865 |
| Reasoning tokens [M] | 2,184 |
| Cache read tokens [M] | 208,896 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **18,255** |
| Thinking ratio [C] | 12.0% |
| Output efficiency [C] | 37.6% |
| Input cost [M] | $0.000793 |
| Output cost [M] | $0.002410 |
| Reasoning cost [M] | $0.000098 |
| Cache cost [M] | $0.009334 |
| **Total cost** | **$0.012634** |
| **Total energy [X]** | **~3342 J** |
| Solution density [C] | 0.025856 LOC/tok |
| Correctness/$ [C] | 20 |
| Quality/J [C] | 0.000145 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0126  |  **Energy:** ~3342J  |  **Thinking:** 12%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_nlme9vjk/session.jsonl)
- [Generated code](./exp_nlme9vjk/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 458 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
