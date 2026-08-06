# Game Report: perturbed-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [silent_sweep:perturbed:natural] Claude_Fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:32:27

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** WASTEFUL
**Score:** 0.310

**Verdict:** WASTEFUL — model burned 846 tokens ($0.2206, ~194J, 0% thinking) achieving only 10% correctness. High reasoning overhead without convergence.

**Recommendation:** Reduce perturbation strength or avoid this operator class.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 5 |
| Quality/J [C] | 0.0052 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 10% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 21 |
| Cyclomatic complexity [C] | 1.0 |
| Code quality [H] | 0.983 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.392** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6 |
| Completion tokens [M] | 840 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 23,388 |
| Cache write tokens [M] | 12,409 |
| **Total tokens** | **846** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.3% |
| Input cost [M] | $0.000060 |
| Output cost [M] | $0.042000 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.178500 |
| **Total cost** | **$0.220560** |
| **Total energy [X]** | **~194 J** |
| Solution density [C] | 0.024823 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.002026 |

---

## Headline Metric
**Strategy:** WASTEFUL  |  **Correctness:** 10%  |  **Cost:** $0.2206  |  **Energy:** ~194J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_Claude_F_np/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 21 |
| Functions | 0 |
| Classes | 2 |
| Functions/file | 0.0 |
| Classes/file | 1.0 |
| Avg lines/file | 10 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 3 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 50%

| Metric | Value |
|--------|-------|
| Output tokens | 840 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0250 LOC/tok |
| **Verdict** | **NARRATION FAILURE — 840 tokens burned, zero code output** |

