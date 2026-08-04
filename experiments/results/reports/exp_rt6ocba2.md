# Game Report: exp_rt6ocba2-baseline

**Model:** openai/gpt-5  |  **Task:** [baseline] quality_gpt_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:58

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.757

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.52) with moderate resource use ($0.1924, ~7739J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 9.1% |
| Quality/$ | 49 |
| Quality/J | 0.0001 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 397 |
| Cyclomatic complexity | 75.0 |
| Code quality | 0.252 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.518** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 46,421 |
| Completion tokens | 6,646 |
| Reasoning tokens | 5,312 |
| **Total tokens** | **58,379** |
| Thinking ratio | 9.1% |
| Output efficiency | 11.4% |
| Input cost | $0.012534 |
| Output cost | $0.007311 |
| Reasoning cost | $0.000744 |
| **Total cost** | **$0.192438** |
| **Total energy** | **~7739 J** |
| Solution density | 0.006800 LOC/tok |
| Correctness/$ | 49 |
| Quality/J | 0.000067 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.1924  |  **Energy:** ~7739J  |  **Thinking:** 9%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 397 |
| Functions | 29 |
| Classes | 4 |
| Functions/file | 14.5 |
| Classes/file | 2.0 |
| Avg lines/file | 198 |
| Type hints | 62% |
| Docstrings | 3% |
| Error handlers | 9 |
| Imports | 22 |
| Decorators | 1 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_rt6ocba2/session.jsonl)

*No code output — this session was narration-only.*