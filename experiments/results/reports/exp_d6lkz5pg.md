# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Building URL shortener with REST API and analytics...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:22:15

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.691

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.67) with moderate resource use ($0.0126, ~3009J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 7.2% |
| Quality/$ [C] | 79 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 67% (4/6 constraints) |
| Lines of code [M] | 227 |
| Cyclomatic complexity [C] | 21.0 |
| Code quality [H] | 0.591 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.673** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,186 |
| Completion tokens [M] | 6,842 |
| Reasoning tokens [M] | 1,320 |
| Cache read tokens [M] | 308,224 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **18,348** |
| Thinking ratio [C] | 7.2% |
| Output efficiency [C] | 37.3% |
| Input cost [M] | $0.000649 |
| Output cost [M] | $0.001776 |
| Reasoning cost [M] | $0.000044 |
| Cache cost [M] | $0.010181 |
| **Total cost** | **$0.012649** |
| **Total energy [X]** | **~3009 J** |
| Solution density [C] | 0.012372 LOC/tok |
| Correctness/$ [C] | 15 |
| Quality/J [C] | 0.000224 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0126  |  **Energy:** ~3009J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_d6lkz5pg/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 4 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 223 |
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
