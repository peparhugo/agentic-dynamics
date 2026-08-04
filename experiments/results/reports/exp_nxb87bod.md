# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_gather_gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:55:14

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.809

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.69) with moderate resource use ($0.7495, ~1912J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.289 |
| Architecture div | 0.000 |
| Structure div | 0.133 |
| Thinking ratio | 7.8% |
| Quality/$ | 127 |
| Quality/J | 0.0005 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 407 |
| Cyclomatic complexity | 80.0 |
| Code quality | 0.246 |
| Novelty vs baseline | 0.829 |
| **Composite** | **0.695** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 33 |
| Completion tokens | 7,079 |
| Reasoning tokens | 598 |
| **Total tokens** | **7,710** |
| Thinking ratio | 7.8% |
| Output efficiency | 91.8% |
| Input cost | $0.000009 |
| Output cost | $0.007787 |
| Reasoning cost | $0.000084 |
| **Total cost** | **$0.749500** |
| **Total energy** | **~1912 J** |
| Solution density | 0.052789 LOC/tok |
| Correctness/$ | 127 |
| Quality/J | 0.000363 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.7495  |  **Energy:** ~1912J  |  **Thinking:** 8%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 407 |
| Functions | 44 |
| Classes | 1 |
| Functions/file | 22.0 |
| Classes/file | 0.5 |
| Avg lines/file | 204 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 12 |
| Decorators | 23 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_nxb87bod/session.jsonl)

*No code output — this session was narration-only.*