# Game Report: web_crawler-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:web_crawler:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:29:40

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.732

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.57) with moderate resource use ($0.0116, ~3571J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 21.3% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 320 |
| Cyclomatic complexity [C] | 83.0 |
| Code quality [H] | 0.312 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.573** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,264 |
| Completion tokens [M] | 4,029 |
| Reasoning tokens [M] | 3,879 |
| Cache read tokens [M] | 70,400 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **18,172** |
| Thinking ratio [C] | 21.3% |
| Output efficiency [C] | 22.2% |
| Input cost [M] | $0.001826 |
| Output cost [M] | $0.002921 |
| Reasoning cost [M] | $0.000358 |
| Cache cost [M] | $0.006495 |
| **Total cost** | **$0.011600** |
| **Total energy [X]** | **~3571 J** |
| Solution density [C] | 0.017610 LOC/tok |
| Correctness/$ [C] | 57 |
| Quality/J [C] | 0.000161 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0116  |  **Energy:** ~3571J  |  **Thinking:** 21%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_web_crawler_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 320 |
| Functions | 33 |
| Classes | 8 |
| Functions/file | 8.2 |
| Classes/file | 2.0 |
| Avg lines/file | 80 |
| Type hints | 73% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 30 |
| Decorators | 2 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
