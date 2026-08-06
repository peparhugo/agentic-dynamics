# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:22:23

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.837

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.98, correctness=100%). Cost: $0.1594, ~4031J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.702 |
| Architecture div [H] | 0.667 |
| Structure div [H] | 0.467 |
| Thinking ratio [C] | 5.1% |
| Quality/$ [C] | 6 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 469 |
| Cyclomatic complexity [C] | 65.0 |
| Code quality [H] | 0.213 |
| Novelty vs baseline [H] | 0.983 |
| **Composite [H]** | **0.540** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18,034 |
| Completion tokens [M] | 8,375 |
| Reasoning tokens [M] | 1,408 |
| Cache read tokens [M] | 312,448 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,817** |
| Thinking ratio [C] | 5.1% |
| Output efficiency [C] | 30.1% |
| Input cost [M] | $0.011386 |
| Output cost [M] | $0.042300 |
| Reasoning cost [M] | $0.007111 |
| Cache cost [M] | $0.098631 |
| **Total cost** | **$0.159429** |
| **Total energy [X]** | **~4031 J** |
| Solution density [C] | 0.016860 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000134 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.1594  |  **Energy:** ~4031J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_dalqefiq/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 16 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 983 |
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
