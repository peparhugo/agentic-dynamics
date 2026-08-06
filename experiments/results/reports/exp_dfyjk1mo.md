# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5.6  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_gather_gpt_5_6...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:47:19

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.791

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.82) with moderate resource use ($0.2848, ~1381J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.352 |
| Architecture div | 0.250 |
| Structure div | 0.130 |
| Thinking ratio | 7.8% |
| Quality/$ | 4 |
| Quality/J | 0.0007 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 100% (7/7 constraints) |
| Lines of code | 310 |
| Cyclomatic complexity | 54.0 |
| Code quality | 0.323 |
| Novelty vs baseline | 0.712 |
| **Composite** | **0.821** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 30 |
| Completion tokens | 5,105 |
| Reasoning tokens | 436 |
| **Total tokens** | **5,571** |
| Thinking ratio | 7.8% |
| Output efficiency | 91.6% |
| **Total cost** | **$0.284770** |
| **Total energy** | **~1381 J** |
| Solution density | 0.055645 LOC/tok |
| Correctness/$ | 176 |
| Quality/J | 0.000595 |

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
