# Game Report: standardized_retry-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [standardized_retry] gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:48:21

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.810

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.58) with moderate resource use ($0.6610, ~1549J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.449 |
| Architecture div | 0.333 |
| Structure div | 0.200 |
| Thinking ratio | 8.9% |
| Quality/$ | 160 |
| Quality/J | 0.0006 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 322 |
| Cyclomatic complexity | 46.0 |
| Code quality | 0.311 |
| Novelty vs baseline | 0.853 |
| **Composite** | **0.583** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 39 |
| Completion tokens | 5,595 |
| Reasoning tokens | 551 |
| **Total tokens** | **6,185** |
| Thinking ratio | 8.9% |
| Output efficiency | 90.5% |
| Input cost | $0.000011 |
| Output cost | $0.006155 |
| Reasoning cost | $0.000077 |
| **Total cost** | **$0.661033** |
| **Total energy** | **~1549 J** |
| Solution density | 0.052061 LOC/tok |
| Correctness/$ | 160 |
| Quality/J | 0.000376 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.6610  |  **Energy:** ~1549J  |  **Thinking:** 9%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 322 |
| Functions | 29 |
| Classes | 1 |
| Functions/file | 14.5 |
| Classes/file | 0.5 |
| Avg lines/file | 161 |
| Type hints | 36% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 15 |
| Decorators | 8 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |
