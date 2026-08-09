# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:38:16

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.61) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $1.5805, ~4430J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.609 |
| Architecture div [H] | 0.615 |
| Structure div [H] | 0.259 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (5/5 tests) [M] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 912 |
| Cyclomatic complexity [C] | 95.0 |
| Code quality [H] | 0.110 |
| Novelty vs baseline [H] | 0.951 |
| **Composite [H]** | **0.530** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 24 |
| Completion tokens [M] | 19,253 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 219,356 |
| Cache write tokens [M] | 31,861 |
| **Total tokens** | **19,277** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000240 |
| Output cost [M] | $0.962650 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.617618 |
| **Total cost** | **$1.580508** |
| **Total energy [X]** | **~4430 J** |
| Solution density [C] | 0.047310 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000120 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $1.5805  |  **Energy:** ~4430J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_pqk11z7c/session.jsonl)
- [Generated code](./exp_pqk11z7c/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 21 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1452 |
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
| Passed | 5 |
| Failed | 0 |
| Errors | 0 |
| Total | 5 |
| Pass rate | 100% |
| Duration | 4.8s |
