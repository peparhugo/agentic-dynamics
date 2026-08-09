# Game Report: standardized_build-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [standardized_build] claude...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:37:40

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.698

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.51) with moderate resource use ($1.1104, ~2910J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.444 |
| Architecture div [H] | 0.455 |
| Structure div [H] | 0.189 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (54/54 tests) [M] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 600 |
| Cyclomatic complexity [C] | 86.0 |
| Code quality [H] | 0.167 |
| Novelty vs baseline [H] | 0.685 |
| **Composite [H]** | **0.510** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 18 |
| Completion tokens [M] | 12,648 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 143,705 |
| Cache write tokens [M] | 26,729 |
| **Total tokens** | **12,666** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000180 |
| Output cost [M] | $0.632400 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.477818 |
| **Total cost** | **$1.110397** |
| **Total energy [X]** | **~2910 J** |
| Solution density [C] | 0.047371 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000175 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $1.1104  |  **Energy:** ~2910J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ovy9g9b5/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 600 |
| Functions | 89 |
| Classes | 14 |
| Functions/file | 8.9 |
| Classes/file | 1.4 |
| Avg lines/file | 60 |
| Type hints | 33% |
| Docstrings | 6% |
| Error handlers | 2 |
| Imports | 32 |
| Decorators | 10 |
| Test files | 5 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 12,648 |
| Python files | 10 |
| Non-Python files | 0 |
| Code density | 0.0474 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 54 |
| Failed | 0 |
| Errors | 0 |
| Total | 54 |
| Pass rate | 100% |
| Duration | 1.1s |
