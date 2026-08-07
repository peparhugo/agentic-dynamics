# Game Report: exp_jcrbm3rt-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** Flask REST API with JWT auth...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:21:55

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.77) with moderate resource use ($0.9687, ~2325J). Attractor basin held. Perturbation was handled in-manifold.

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
| Quality/J [C] | 0.0004 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 432 |
| Cyclomatic complexity [C] | 116.0 |
| Code quality [H] | 0.231 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.771** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 26 |
| Completion tokens [M] | 10,098 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 191,230 |
| Cache write tokens [M] | 21,787 |
| **Total tokens** | **10,124** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.7% |
| Input cost [M] | $0.000260 |
| Output cost [M] | $0.504900 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.463568 |
| **Total cost** | **$0.968727** |
| **Total energy [X]** | **~2325 J** |
| Solution density [C] | 0.042671 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000332 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.9687  |  **Energy:** ~2325J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_jcrbm3rt/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 432 |
| Functions | 33 |
| Classes | 9 |
| Functions/file | 4.1 |
| Classes/file | 1.1 |
| Avg lines/file | 54 |
| Type hints | 30% |
| Docstrings | 27% |
| Error handlers | 5 |
| Imports | 30 |
| Decorators | 7 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
