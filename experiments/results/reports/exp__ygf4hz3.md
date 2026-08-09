# Game Report: exp__ygf4hz3-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:24:40

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.712

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.53) with moderate resource use ($0.0337, ~10636J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 31.3% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 910 |
| Cyclomatic complexity [C] | 114.0 |
| Code quality [H] | 0.110 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.533** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 17,781 |
| Completion tokens [M] | 12,155 |
| Reasoning tokens [M] | 13,654 |
| Cache read tokens [M] | 969,344 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **43,590** |
| Thinking ratio [C] | 31.3% |
| Output efficiency [C] | 27.9% |
| Input cost [M] | $0.001039 |
| Output cost [M] | $0.002892 |
| Reasoning cost [M] | $0.000414 |
| Cache cost [M] | $0.029358 |
| **Total cost** | **$0.033702** |
| **Total energy [X]** | **~10636 J** |
| Solution density [C] | 0.020876 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000050 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0337  |  **Energy:** ~10636J  |  **Thinking:** 31%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp__ygf4hz3/session.jsonl)
- [Generated code](./exp__ygf4hz3/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 14 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 894 |
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
