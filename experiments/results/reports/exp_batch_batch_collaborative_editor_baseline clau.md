# Game Report: collaborative_editor-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [batch:collaborative_editor:baseline] claude_fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:46:35

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.670

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.64) with moderate resource use ($2.4895, ~6935J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 30 |
| Quality/J | 0.0001 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (62/62 tests) |
| Constraint satisfaction | 0% (0/4 constraints) |
| Lines of code | 1074 |
| Cyclomatic complexity | 235.0 |
| Code quality | 0.093 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.639** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 32 |
| Completion tokens | 30,139 |
| Reasoning tokens | 0 |
| **Total tokens** | **30,171** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| Input cost | $0.000009 |
| Output cost | $0.033153 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$2.489478** |
| **Total energy** | **~6935 J** |
| Solution density | 0.035597 LOC/tok |
| Correctness/$ | 21 |
| Quality/J | 0.000092 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $2.4895  |  **Energy:** ~6935J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_batch_collaborative_editor_baseline clau/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 14 |
| Total lines (Py) | 1074 |
| Functions | 136 |
| Classes | 15 |
| Functions/file | 9.7 |
| Classes/file | 1.1 |
| Avg lines/file | 77 |
| Type hints | 46% |
| Docstrings | 7% |
| Error handlers | 0 |
| Imports | 39 |
| Decorators | 2 |
| Test files | 7 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 30,139 |
| Python files | 14 |
| Non-Python files | 0 |
| Code density | 0.0356 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |



---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 62 |
| Failed | 0 |
| Errors | 0 |
| Total | 62 |
| Pass rate | 100% |
| Duration | 0.6s |
