# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** URL shortener: collision-resistance & analytics...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:22:08

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.701

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.69) with moderate resource use ($0.0098, ~2194J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 3.4% |
| Quality/$ [C] | 102 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 67% (4/6 constraints) |
| Lines of code [M] | 146 |
| Cyclomatic complexity [C] | 19.0 |
| Code quality [H] | 0.683 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.692** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,910 |
| Completion tokens [M] | 5,032 |
| Reasoning tokens [M] | 518 |
| Cache read tokens [M] | 181,632 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **15,460** |
| Thinking ratio [C] | 3.4% |
| Output efficiency [C] | 32.5% |
| Input cost [M] | $0.000778 |
| Output cost [M] | $0.001609 |
| Reasoning cost [M] | $0.000021 |
| Cache cost [M] | $0.007390 |
| **Total cost** | **$0.009798** |
| **Total energy [X]** | **~2194 J** |
| Solution density [C] | 0.009444 LOC/tok |
| Correctness/$ [C] | 24 |
| Quality/J [C] | 0.000315 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0098  |  **Energy:** ~2194J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_cqc0vqav/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| JS files | 4 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 142 |
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
