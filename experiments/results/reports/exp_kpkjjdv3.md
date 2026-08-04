# Game Report: standardized_build-perturbed

**Model:** openai/gpt-5.6  |  **Task:** [standardized_build] gpt-5.6...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:53:59

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.797

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.58) with moderate resource use ($0.2664, ~1242J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.459 |
| Architecture div | 0.400 |
| Structure div | 0.263 |
| Thinking ratio | 6.8% |
| Quality/$ | 192 |
| Quality/J | 0.0008 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 268 |
| Cyclomatic complexity | 32.0 |
| Code quality | 0.373 |
| Novelty vs baseline | 0.735 |
| **Composite** | **0.578** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 30 |
| Completion tokens | 4,690 |
| Reasoning tokens | 343 |
| **Total tokens** | **5,063** |
| Thinking ratio | 6.8% |
| Output efficiency | 92.6% |
| Input cost | $0.000008 |
| Output cost | $0.005159 |
| Reasoning cost | $0.000048 |
| **Total cost** | **$0.266403** |
| **Total energy** | **~1242 J** |
| Solution density | 0.052933 LOC/tok |
| Correctness/$ | 192 |
| Quality/J | 0.000465 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.2664  |  **Energy:** ~1242J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 268 |
| Functions | 27 |
| Classes | 1 |
| Functions/file | 13.5 |
| Classes/file | 0.5 |
| Avg lines/file | 134 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 2 |
| Imports | 14 |
| Decorators | 10 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_kpkjjdv3/code/)
