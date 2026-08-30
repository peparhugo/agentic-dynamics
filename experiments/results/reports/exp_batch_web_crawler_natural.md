# Game Report: web_crawler-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:web_crawler:baseline] ds_natural...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:26

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.812

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.56) with moderate resource use ($0.0640, ~20850J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 37.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 1977 |
| Cyclomatic complexity [C] | 437.0 |
| Code quality [H] | 0.051 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.564** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 13,335 |
| Completion tokens [M] | 31,156 |
| Reasoning tokens [M] | 26,846 |
| Cache read tokens [M] | 2,140,672 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **71,337** |
| Thinking ratio [C] | 37.6% |
| Output efficiency [C] | 43.7% |
| Input cost [M] | $0.003300 |
| Output cost [M] | $0.023132 |
| Reasoning cost [M] | $0.019932 |
| Cache cost [M] | $0.017659 |
| **Total cost** | **$0.064022** |
| **Total energy [X]** | **~20850 J** |
| Solution density [C] | 0.027714 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000027 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0640  |  **Energy:** ~20850J  |  **Thinking:** 38%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_web_crawler_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 24 |
| Total lines (Py) | 1977 |
| Functions | 226 |
| Classes | 25 |
| Functions/file | 9.4 |
| Classes/file | 1.0 |
| Avg lines/file | 82 |
| Type hints | 57% |
| Docstrings | 9% |
| Error handlers | 5 |
| Imports | 98 |
| Decorators | 10 |
| Test files | 12 |
| Test file rate | 50% |
| Parse errors | 0 |
