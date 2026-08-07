# Game Report: exp_ednngz36-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** REST API with JWT & rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:19:48

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.77) with moderate resource use ($0.9377, ~2149J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 456 |
| Cyclomatic complexity [C] | 116.0 |
| Code quality [H] | 0.219 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.769** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 28 |
| Completion tokens [M] | 9,333 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 206,926 |
| Cache write tokens [M] | 21,109 |
| **Total tokens** | **9,361** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.7% |
| Input cost [M] | $0.000280 |
| Output cost [M] | $0.466650 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.470789 |
| **Total cost** | **$0.937719** |
| **Total energy [X]** | **~2149 J** |
| Solution density [C] | 0.048713 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000358 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.9377  |  **Energy:** ~2149J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ednngz36/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 456 |
| Functions | 40 |
| Classes | 12 |
| Functions/file | 4.0 |
| Classes/file | 1.2 |
| Avg lines/file | 46 |
| Type hints | 0% |
| Docstrings | 8% |
| Error handlers | 6 |
| Imports | 28 |
| Decorators | 8 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
