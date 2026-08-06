# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5.6  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_gather_gpt_5_6...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:22:32

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.791

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.82) with moderate resource use ($0.2848, ~1381J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.352 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.130 |
| Thinking ratio [C] | 7.8% |
| Quality/$ [C] | 4 |
| Quality/J [C] | 0.0007 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (13/13 tests) [M] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 310 |
| Cyclomatic complexity [C] | 54.0 |
| Code quality [H] | 0.323 |
| Novelty vs baseline [H] | 0.712 |
| **Composite [H]** | **0.821** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 30 |
| Completion tokens [M] | 5,105 |
| Reasoning tokens [M] | 436 |
| Cache read tokens [M] | 78,367 |
| Cache write tokens [M] | 12,673 |
| **Total tokens** | **5,571** |
| Thinking ratio [C] | 7.8% |
| Output efficiency [C] | 91.6% |
| Input cost [M] | $0.000078 |
| Output cost [M] | $0.106807 |
| Reasoning cost [M] | $0.009122 |
| Cache cost [M] | $0.168762 |
| **Total cost** | **$0.284770** |
| **Total energy [X]** | **~1381 J** |
| Solution density [C] | 0.055645 LOC/tok |
| Correctness/$ [C] | 7 |
| Quality/J [C] | 0.000595 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.2848  |  **Energy:** ~1381J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_dfyjk1mo/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 310 |
| Functions | 38 |
| Classes | 2 |
| Functions/file | 19.0 |
| Classes/file | 1.0 |
| Avg lines/file | 155 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 16 |
| Decorators | 21 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 13 |
| Failed | 0 |
| Errors | 0 |
| Total | 13 |
| Pass rate | 100% |
| Duration | 1.2s |
