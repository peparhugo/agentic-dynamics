# Game Report: exp_zpgio1qs-baseline

**Model:** openai/gpt-5  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:46:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.688

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.48) with moderate resource use ($0.2201, ~7179J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 8.5% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 514 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.195 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.480** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 36,516 |
| Completion tokens [M] | 9,750 |
| Reasoning tokens [M] | 4,288 |
| Cache read tokens [M] | 272,768 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **50,554** |
| Thinking ratio [C] | 8.5% |
| Output efficiency [C] | 19.3% |
| Input cost [M] | $0.028183 |
| Output cost [M] | $0.060201 |
| Reasoning cost [M] | $0.026476 |
| Cache cost [M] | $0.105261 |
| **Total cost** | **$0.220121** |
| **Total energy [X]** | **~7179 J** |
| Solution density [C] | 0.010167 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000067 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.2201  |  **Energy:** ~7179J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_zpgio1qs/session.jsonl)
- [Generated code](./exp_zpgio1qs/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 493 |
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
