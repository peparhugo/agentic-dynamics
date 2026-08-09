# Game Report: exp_3j2vrct4-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** REST API: JWT, rate limiting, audit logging...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:20:12

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.77) with moderate resource use ($0.8723, ~2220J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 463 |
| Cyclomatic complexity [C] | 94.0 |
| Code quality [H] | 0.216 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.768** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18 |
| Completion tokens [M] | 9,644 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 117,871 |
| Cache write tokens [M] | 21,760 |
| **Total tokens** | **9,662** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000180 |
| Output cost [M] | $0.482200 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.389871 |
| **Total cost** | **$0.872251** |
| **Total energy [X]** | **~2220 J** |
| Solution density [C] | 0.047920 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000346 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.8723  |  **Energy:** ~2220J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_3j2vrct4/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 463 |
| Functions | 36 |
| Classes | 10 |
| Functions/file | 3.6 |
| Classes/file | 1.0 |
| Avg lines/file | 46 |
| Type hints | 36% |
| Docstrings | 14% |
| Error handlers | 7 |
| Imports | 36 |
| Decorators | 15 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
