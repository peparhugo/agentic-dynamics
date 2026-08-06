# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5_r1] cd_claude_2rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:15:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.818

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.80) with moderate resource use ($0.9876, ~2689J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.366 |
| Architecture div [H] | 0.200 |
| Structure div [H] | 0.164 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 562 |
| Cyclomatic complexity [C] | 96.0 |
| Code quality [H] | 0.178 |
| Novelty vs baseline [H] | 0.790 |
| **Composite [H]** | **0.804** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20 |
| Completion tokens [M] | 11,684 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 133,020 |
| Cache write tokens [M] | 21,617 |
| **Total tokens** | **11,704** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000200 |
| Output cost [M] | $0.584200 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.403232 |
| **Total cost** | **$0.987632** |
| **Total energy [X]** | **~2689 J** |
| Solution density [C] | 0.048018 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000299 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.9876  |  **Energy:** ~2689J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_6wexzcci/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 12 |
| Total lines (Py) | 562 |
| Functions | 44 |
| Classes | 11 |
| Functions/file | 3.7 |
| Classes/file | 0.9 |
| Avg lines/file | 47 |
| Type hints | 26% |
| Docstrings | 7% |
| Error handlers | 7 |
| Imports | 46 |
| Decorators | 21 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
