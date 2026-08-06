# Game Report: baseline-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:baseline:forced] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:04:47

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.650

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.58) with moderate resource use ($0.0271, ~3960J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 10.1% |
| Quality/$ | 92 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (4/4 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 227 |
| Cyclomatic complexity | 41.0 |
| Code quality | 0.441 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.580** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 19,613 |
| Completion tokens | 4,770 |
| Reasoning tokens | 2,752 |
| **Total tokens** | **27,135** |
| Thinking ratio | 10.1% |
| Output efficiency | 17.6% |
| Input cost | $0.005296 |
| Output cost | $0.005247 |
| Reasoning cost | $0.000385 |
| **Total cost** | **$0.027134** |
| **Total energy** | **~3960 J** |
| Solution density | 0.008366 LOC/tok |
| Correctness/$ | 64 |
| Quality/J | 0.000146 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0271  |  **Energy:** ~3960J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_sweep_gpt_5_mini_fb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 227 |
| Functions | 20 |
| Classes | 3 |
| Functions/file | 10.0 |
| Classes/file | 1.5 |
| Avg lines/file | 114 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 9 |
| Decorators | 12 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,770 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0476 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 4 |
| Failed | 0 |
| Errors | 0 |
| Total | 4 |
| Pass rate | 100% |
| Duration | 1.8s |
