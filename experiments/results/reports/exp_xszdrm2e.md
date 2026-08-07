# Game Report: exp_xszdrm2e-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask REST API: JWT, rate limiting & audit logging...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:27:57

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.769

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0142, ~3406J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 2.8% |
| Quality/$ [C] | 71 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 809 |
| Cyclomatic complexity [C] | 52.0 |
| Code quality [H] | 0.124 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.750** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,020 |
| Completion tokens [M] | 10,518 |
| Reasoning tokens [M] | 564 |
| Cache read tokens [M] | 170,368 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,102** |
| Thinking ratio [C] | 2.8% |
| Output efficiency [C] | 52.3% |
| Input cost [M] | $0.000910 |
| Output cost [M] | $0.004325 |
| Reasoning cost [M] | $0.000030 |
| Cache cost [M] | $0.008917 |
| **Total cost** | **$0.014183** |
| **Total energy [X]** | **~3406 J** |
| Solution density [C] | 0.040245 LOC/tok |
| Correctness/$ [C] | 26 |
| Quality/J [C] | 0.000220 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0142  |  **Energy:** ~3406J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_xszdrm2e/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 20 |
| Total lines (Py) | 809 |
| Functions | 89 |
| Classes | 14 |
| Functions/file | 4.5 |
| Classes/file | 0.7 |
| Avg lines/file | 40 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 12 |
| Imports | 49 |
| Decorators | 59 |
| Test files | 7 |
| Test file rate | 35% |
| Parse errors | 0 |
