# Game Report: twitter_timeline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:twitter_timeline:baseline] ds_natural...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:03

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.817

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.50) with moderate resource use ($0.0117, ~4150J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 36.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 266 |
| Cyclomatic complexity [C] | 68.0 |
| Code quality [H] | 0.376 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.500** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6,444 |
| Completion tokens [M] | 3,900 |
| Reasoning tokens [M] | 5,824 |
| Cache read tokens [M] | 131,200 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **16,168** |
| Thinking ratio [C] | 36.0% |
| Output efficiency [C] | 24.1% |
| Input cost [M] | $0.001892 |
| Output cost [M] | $0.003434 |
| Reasoning cost [M] | $0.005129 |
| Cache cost [M] | $0.001284 |
| **Total cost** | **$0.011739** |
| **Total energy [X]** | **~4150 J** |
| Solution density [C] | 0.016452 LOC/tok |
| Correctness/$ [C] | 38 |
| Quality/J [C] | 0.000121 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0117  |  **Energy:** ~4150J  |  **Thinking:** 36%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_twitter_timeline_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 266 |
| Functions | 29 |
| Classes | 4 |
| Functions/file | 4.1 |
| Classes/file | 0.6 |
| Avg lines/file | 38 |
| Type hints | 69% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 19 |
| Decorators | 0 |
| Test files | 2 |
| Test file rate | 29% |
| Parse errors | 0 |
