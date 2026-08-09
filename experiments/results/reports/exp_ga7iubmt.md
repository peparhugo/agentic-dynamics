# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:32:49

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.795

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.77) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0350, ~10475J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.766 |
| Architecture div [H] | 0.900 |
| Structure div [H] | 0.383 |
| Thinking ratio [C] | 25.4% |
| Quality/$ [C] | 29 |
| Quality/J [C] | 0.0001 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (3/3 tests) [M] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 947 |
| Cyclomatic complexity [C] | 75.0 |
| Code quality [H] | 0.106 |
| Novelty vs baseline [H] | 0.971 |
| **Composite [H]** | **0.560** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16,270 |
| Completion tokens [M] | 16,847 |
| Reasoning tokens [M] | 11,273 |
| Cache read tokens [M] | 962,304 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **44,390** |
| Thinking ratio [C] | 25.4% |
| Output efficiency [C] | 38.0% |
| Input cost [M] | $0.000966 |
| Output cost [M] | $0.004077 |
| Reasoning cost [M] | $0.000347 |
| Cache cost [M] | $0.029639 |
| **Total cost** | **$0.035030** |
| **Total energy [X]** | **~10475 J** |
| Solution density [C] | 0.021334 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000053 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0350  |  **Energy:** ~10475J  |  **Thinking:** 25%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ga7iubmt/session.jsonl)
- [Generated code](./exp_ga7iubmt/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 11 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 926 |
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


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 3 |
| Failed | 0 |
| Errors | 0 |
| Total | 3 |
| Pass rate | 100% |
| Duration | 3.7s |
