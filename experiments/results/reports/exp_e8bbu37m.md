# Game Report: exp_e8bbu37m-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [baseline] cd_claude_2rep...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:52:34

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.77) with moderate resource use ($0.9975, ~2593J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 81 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 100% (7/7 constraints) |
| Lines of code | 459 |
| Cyclomatic complexity | 53.0 |
| Code quality | 0.218 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.769** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 22 |
| Completion tokens | 11,265 |
| Reasoning tokens | 0 |
| **Total tokens** | **11,287** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000006 |
| Output cost | $0.012392 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.997524** |
| **Total energy** | **~2593 J** |
| Solution density | 0.040666 LOC/tok |
| Correctness/$ | 81 |
| Quality/J | 0.000296 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.9975  |  **Energy:** ~2593J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_e8bbu37m/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 459 |
| Functions | 36 |
| Classes | 17 |
| Functions/file | 2.8 |
| Classes/file | 1.3 |
| Avg lines/file | 35 |
| Type hints | 14% |
| Docstrings | 8% |
| Error handlers | 4 |
| Imports | 47 |
| Decorators | 29 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
