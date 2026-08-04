# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5.6  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_gather_gpt_5_6...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:44:14

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.812

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.74) with moderate resource use ($0.3341, ~1672J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.252 |
| Architecture div | 0.000 |
| Structure div | 0.015 |
| Thinking ratio | 6.0% |
| Quality/$ | 140 |
| Quality/J | 0.0006 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 407 |
| Cyclomatic complexity | 70.0 |
| Code quality | 0.246 |
| Novelty vs baseline | 0.825 |
| **Composite** | **0.737** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 30 |
| Completion tokens | 6,419 |
| Reasoning tokens | 412 |
| **Total tokens** | **6,861** |
| Thinking ratio | 6.0% |
| Output efficiency | 93.6% |
| Input cost | $0.000008 |
| Output cost | $0.007061 |
| Reasoning cost | $0.000058 |
| **Total cost** | **$0.334122** |
| **Total energy** | **~1672 J** |
| Solution density | 0.059321 LOC/tok |
| Correctness/$ | 140 |
| Quality/J | 0.000441 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3341  |  **Energy:** ~1672J  |  **Thinking:** 6%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines | 407 |
| Functions | 34 |
| Classes | 0 |
| Functions/file | 11.3 |
| Classes/file | 0.0 |
| Avg lines/file | 136 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 12 |
| Decorators | 22 |
| Test files | 1 |
| Test file rate | 33% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_1d30evhp/session.jsonl)

*No code output — this session was narration-only.*