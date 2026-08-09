# Game Report: exp_3hlb2bus-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** Task management API: Flask/SQLite/JWT...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:13:59

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.67) with moderate resource use ($1.2564, ~3282J). Attractor basin held. Perturbation was handled in-manifold.

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
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 581 |
| Cyclomatic complexity [C] | 134.0 |
| Code quality [H] | 0.172 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.674** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 28 |
| Completion tokens [M] | 14,260 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 210,597 |
| Cache write tokens [M] | 26,605 |
| **Total tokens** | **14,288** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000280 |
| Output cost [M] | $0.713000 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.543160 |
| **Total cost** | **$1.256440** |
| **Total energy [X]** | **~3282 J** |
| Solution density [C] | 0.040663 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000205 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $1.2564  |  **Energy:** ~3282J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_3hlb2bus/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 581 |
| Functions | 45 |
| Classes | 3 |
| Functions/file | 5.6 |
| Classes/file | 0.4 |
| Avg lines/file | 73 |
| Type hints | 22% |
| Docstrings | 13% |
| Error handlers | 6 |
| Imports | 29 |
| Decorators | 34 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
