# Game Report: baseline-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:baseline:natural] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:40:52

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.656

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.64) with moderate resource use ($0.0595, ~8288J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 6.8% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 75% (3/4 tests) [M] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 342 |
| Cyclomatic complexity [C] | 58.0 |
| Code quality [H] | 0.292 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.636** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 48,201 |
| Completion tokens [M] | 10,507 |
| Reasoning tokens [M] | 4,288 |
| Cache read tokens [M] | 716,160 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **62,996** |
| Thinking ratio [C] | 6.8% |
| Output efficiency [C] | 16.7% |
| Input cost [M] | $0.005471 |
| Output cost [M] | $0.009540 |
| Reasoning cost [M] | $0.003893 |
| Cache cost [M] | $0.040640 |
| **Total cost** | **$0.059544** |
| **Total energy [X]** | **~8288 J** |
| Solution density [C] | 0.005429 LOC/tok |
| Correctness/$ [C] | 1 |
| Quality/J [C] | 0.000077 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 75%  |  **Cost:** $0.0595  |  **Energy:** ~8288J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_mini_nb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 342 |
| Functions | 28 |
| Classes | 4 |
| Functions/file | 3.5 |
| Classes/file | 0.5 |
| Avg lines/file | 43 |
| Type hints | 0% |
| Docstrings | 4% |
| Error handlers | 5 |
| Imports | 33 |
| Decorators | 14 |
| Test files | 2 |
| Test file rate | 25% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 10,507 |
| Python files | 8 |
| Non-Python files | 0 |
| Code density | 0.0325 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 3 |
| Failed | 1 |
| Errors | 0 |
| Total | 4 |
| Pass rate | 75% |
| Duration | 3.8s |
