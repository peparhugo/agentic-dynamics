# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [inject_phantom_success_s0.5_r1] cd_openai_GPT_5_mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:31:25

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.708

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.76) with moderate resource use ($0.0211, ~3092J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.384 |
| Architecture div [H] | 0.250 |
| Structure div [H] | 0.091 |
| Thinking ratio [C] | 7.9% |
| Quality/$ [C] | 47 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (5/5 tests) [M] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 233 |
| Cyclomatic complexity [C] | 42.0 |
| Code quality [H] | 0.429 |
| Novelty vs baseline [H] | 0.857 |
| **Composite [H]** | **0.759** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 14,243 |
| Completion tokens [M] | 5,088 |
| Reasoning tokens [M] | 1,664 |
| Cache read tokens [M] | 162,176 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **20,995** |
| Thinking ratio [C] | 7.9% |
| Output efficiency [C] | 24.2% |
| Input cost [M] | $0.002014 |
| Output cost [M] | $0.005756 |
| Reasoning cost [M] | $0.001882 |
| Cache cost [M] | $0.011467 |
| **Total cost** | **$0.021119** |
| **Total energy [X]** | **~3092 J** |
| Solution density [C] | 0.011098 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000246 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0211  |  **Energy:** ~3092J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ejk4tssk/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 233 |
| Functions | 26 |
| Classes | 1 |
| Functions/file | 3.7 |
| Classes/file | 0.1 |
| Avg lines/file | 33 |
| Type hints | 4% |
| Docstrings | 4% |
| Error handlers | 6 |
| Imports | 28 |
| Decorators | 12 |
| Test files | 1 |
| Test file rate | 14% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 5,088 |
| Python files | 7 |
| Non-Python files | 0 |
| Code density | 0.0458 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 5 |
| Failed | 0 |
| Errors | 0 |
| Total | 5 |
| Pass rate | 100% |
| Duration | 2.7s |
