# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** openai/gpt-5.5  |  **Task:** [remove_critical_constraint_s0.5_r1] gpt_gather_gpt_5_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:24:31

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.826

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.86) with moderate resource use ($0.3050, ~2980J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.468 |
| Architecture div [H] | 0.500 |
| Structure div [H] | 0.042 |
| Thinking ratio [C] | 0.8% |
| Quality/$ [C] | 3 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (11/11 tests) [M] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 251 |
| Cyclomatic complexity [C] | 41.0 |
| Code quality [H] | 0.398 |
| Novelty vs baseline [H] | 0.852 |
| **Composite [H]** | **0.857** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 22,181 |
| Completion tokens [M] | 4,771 |
| Reasoning tokens [M] | 230 |
| Cache read tokens [M] | 88,064 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,182** |
| Thinking ratio [C] | 0.8% |
| Output efficiency [C] | 17.6% |
| Input cost [M] | $0.063683 |
| Output cost [M] | $0.109583 |
| Reasoning cost [M] | $0.005283 |
| Cache cost [M] | $0.126419 |
| **Total cost** | **$0.304967** |
| **Total energy [X]** | **~2980 J** |
| Solution density [C] | 0.009234 LOC/tok |
| Correctness/$ [C] | 8 |
| Quality/J [C] | 0.000288 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3050  |  **Energy:** ~2980J  |  **Thinking:** 1%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp__gihw__t/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 251 |
| Functions | 34 |
| Classes | 2 |
| Functions/file | 17.0 |
| Classes/file | 1.0 |
| Avg lines/file | 126 |
| Type hints | 43% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 13 |
| Decorators | 13 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 11 |
| Failed | 0 |
| Errors | 0 |
| Total | 11 |
| Pass rate | 100% |
| Duration | 0.8s |
