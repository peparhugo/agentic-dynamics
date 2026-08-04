# Game Report: perturbed-baseline

**Model:** openai/gpt-5.6  |  **Task:** [silent_sweep:perturbed:natural] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:58

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.760

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.4235, ~2264J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.5% |
| Quality/$ | 107 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 618 |
| Cyclomatic complexity | 73.0 |
| Code quality | 0.162 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.715** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 30 |
| Completion tokens | 8,426 |
| Reasoning tokens | 689 |
| **Total tokens** | **9,145** |
| Thinking ratio | 7.5% |
| Output efficiency | 92.1% |
| Input cost | $0.000008 |
| Output cost | $0.009269 |
| Reasoning cost | $0.000096 |
| **Total cost** | **$0.423538** |
| **Total energy** | **~2264 J** |
| Solution density | 0.067578 LOC/tok |
| Correctness/$ | 107 |
| Quality/J | 0.000316 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.4235  |  **Energy:** ~2264J  |  **Thinking:** 8%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 11 |
| Total lines | 618 |
| Functions | 58 |
| Classes | 5 |
| Functions/file | 5.3 |
| Classes/file | 0.5 |
| Avg lines/file | 56 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 48 |
| Decorators | 39 |
| Test files | 2 |
| Test file rate | 18% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_sweep_gpt_5_6_np/session.jsonl)

*No code output — this session was narration-only.*