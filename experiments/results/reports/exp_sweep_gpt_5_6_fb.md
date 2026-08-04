# Game Report: baseline-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:baseline:forced] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:58

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.761

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.60) with moderate resource use ($0.3088, ~1674J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.0% |
| Quality/$ | 143 |
| Quality/J | 0.0006 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 427 |
| Cyclomatic complexity | 85.0 |
| Code quality | 0.234 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.600** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18 |
| Completion tokens | 6,304 |
| Reasoning tokens | 474 |
| **Total tokens** | **6,796** |
| Thinking ratio | 7.0% |
| Output efficiency | 92.8% |
| Input cost | $0.000005 |
| Output cost | $0.006934 |
| Reasoning cost | $0.000066 |
| **Total cost** | **$0.308753** |
| **Total energy** | **~1674 J** |
| Solution density | 0.062831 LOC/tok |
| Correctness/$ | 143 |
| Quality/J | 0.000359 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3088  |  **Energy:** ~1674J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 427 |
| Functions | 43 |
| Classes | 4 |
| Functions/file | 21.5 |
| Classes/file | 2.0 |
| Avg lines/file | 214 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 13 |
| Decorators | 33 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |
