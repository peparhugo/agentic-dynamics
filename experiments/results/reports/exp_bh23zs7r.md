# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:29:47

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.757

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.98, correctness=80%). Cost: $0.1477, ~4399J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.703 |
| Architecture div [H] | 0.667 |
| Structure div [H] | 0.469 |
| Thinking ratio [C] | 10.2% |
| Quality/$ [C] | 7 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (1/5 tests) [M] |
| Constraint satisfaction [H] | 14% (1/7 constraints) |
| Lines of code [M] | 475 |
| Cyclomatic complexity [C] | 72.0 |
| Code quality [H] | 0.211 |
| Novelty vs baseline [H] | 0.983 |
| **Composite [H]** | **0.512** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 15,390 |
| Completion tokens [M] | 8,280 |
| Reasoning tokens [M] | 2,688 |
| Cache read tokens [M] | 150,656 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **26,358** |
| Thinking ratio [C] | 10.2% |
| Output efficiency [C] | 31.4% |
| Input cost [M] | $0.012741 |
| Output cost [M] | $0.054840 |
| Reasoning cost [M] | $0.017803 |
| Cache cost [M] | $0.062364 |
| **Total cost** | **$0.147749** |
| **Total energy [X]** | **~4399 J** |
| Solution density [C] | 0.018021 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000117 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.1477  |  **Energy:** ~4399J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_bh23zs7r/session.jsonl)
- [Generated code](./exp_bh23zs7r/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 447 |
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
| Passed | 1 |
| Failed | 0 |
| Errors | 0 |
| Total | 5 |
| Pass rate | 100% |
| Duration | 3.9s |
