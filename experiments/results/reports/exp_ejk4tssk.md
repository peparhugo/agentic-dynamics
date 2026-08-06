# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5-mini  |  **Task:** [inject_phantom_success_s0.5_r1] cd_openai_GPT_5_mini...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:53:12

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.708

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.76) with moderate resource use ($0.0211, ~3092J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.384 |
| Architecture div | 0.250 |
| Structure div | 0.091 |
| Thinking ratio | 7.9% |
| Quality/$ | 103 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (5/5 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 233 |
| Cyclomatic complexity | 42.0 |
| Code quality | 0.429 |
| Novelty vs baseline | 0.857 |
| **Composite** | **0.759** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 14,243 |
| Completion tokens | 5,088 |
| Reasoning tokens | 1,664 |
| **Total tokens** | **20,995** |
| Thinking ratio | 7.9% |
| Output efficiency | 24.2% |
| Input cost | $0.003846 |
| Output cost | $0.005597 |
| Reasoning cost | $0.000233 |
| **Total cost** | **$0.021119** |
| **Total energy** | **~3092 J** |
| Solution density | 0.011098 LOC/tok |
| Correctness/$ | 72 |
| Quality/J | 0.000246 |

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
| Duration | 10.9s |
