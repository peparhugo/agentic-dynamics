# Game Report: exp_e8bbu37m-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [baseline] cd_claude_2rep...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:19:32

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.77) with moderate resource use ($0.9975, ~2593J). Attractor basin held. Perturbation was handled in-manifold.

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
| Quality/J [C] | 0.0004 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 459 |
| Cyclomatic complexity [C] | 53.0 |
| Code quality [H] | 0.218 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.769** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 22 |
| Completion tokens [M] | 11,265 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 154,841 |
| Cache write tokens [M] | 22,337 |
| **Total tokens** | **11,287** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000220 |
| Output cost [M] | $0.563250 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.434054 |
| **Total cost** | **$0.997524** |
| **Total energy [X]** | **~2593 J** |
| Solution density [C] | 0.040666 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000296 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.9975  |  **Energy:** ~2593J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_e8bbu37m/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 459 |
| Functions | 36 |
| Classes | 17 |
| Functions/file | 2.8 |
| Classes/file | 1.3 |
| Avg lines/file | 35 |
| Type hints | 14% |
| Docstrings | 8% |
| Error handlers | 4 |
| Imports | 47 |
| Decorators | 29 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
