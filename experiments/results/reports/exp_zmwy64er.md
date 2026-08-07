# Game Report: exp_zmwy64er-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [debug_forced] deepseek...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:28:59

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.347

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=0%, quality=0.31) with moderate resource use ($0.0043, ~984J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 6.5% |
| Quality/$ [C] | 0 |
| Quality/J [C] | 0.0000 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 0% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 11 |
| Cyclomatic complexity [C] | 1.0 |
| Code quality [H] | 0.983 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.315** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,154 |
| Completion tokens [M] | 670 |
| Reasoning tokens [M] | 548 |
| Cache read tokens [M] | 35,584 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **8,372** |
| Thinking ratio [C] | 6.5% |
| Output efficiency [C] | 8.0% |
| Input cost [M] | $0.001075 |
| Output cost [M] | $0.000410 |
| Reasoning cost [M] | $0.000043 |
| Cache cost [M] | $0.002773 |
| **Total cost** | **$0.004301** |
| **Total energy [X]** | **~984 J** |
| Solution density [C] | 0.001314 LOC/tok |
| Correctness/$ [C] | 0 |
| Quality/J [C] | 0.000320 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 0%  |  **Cost:** $0.0043  |  **Energy:** ~984J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_zmwy64er/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| Total lines (Py) | 11 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0.0 |
| Classes/file | 0.0 |
| Avg lines/file | 11 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 1 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 50%

| Metric | Value |
|--------|-------|
| Output tokens | 670 |
| Python files | 1 |
| Non-Python files | 0 |
| Code density | 0.0164 LOC/tok |
| **Verdict** | **NARRATION FAILURE — 670 tokens burned, zero code output** |

