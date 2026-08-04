# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r1] cd_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:57:34

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.823

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0106, ~2426J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.429 |
| Architecture div | 0.333 |
| Structure div | 0.098 |
| Thinking ratio | 5.0% |
| Quality/$ | 111 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 372 |
| Cyclomatic complexity | 50.0 |
| Code quality | 0.269 |
| Novelty vs baseline | 0.889 |
| **Composite** | **0.709** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,508 |
| Completion tokens | 6,024 |
| Reasoning tokens | 765 |
| **Total tokens** | **15,297** |
| Thinking ratio | 5.0% |
| Output efficiency | 39.4% |
| Input cost | $0.002297 |
| Output cost | $0.006626 |
| Reasoning cost | $0.000107 |
| **Total cost** | **$0.010612** |
| **Total energy** | **~2426 J** |
| Solution density | 0.024318 LOC/tok |
| Correctness/$ | 111 |
| Quality/J | 0.000292 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0106  |  **Energy:** ~2426J  |  **Thinking:** 5%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 20 |
| Total lines | 372 |
| Functions | 41 |
| Classes | 5 |
| Functions/file | 2.0 |
| Classes/file | 0.2 |
| Avg lines/file | 19 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 12 |
| Imports | 43 |
| Decorators | 47 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_uaqvwo_n/session.jsonl)

*No code output — this session was narration-only.*