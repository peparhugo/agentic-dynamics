# Game Report: twitter_timeline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:twitter_timeline:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:51:13

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.51) with moderate resource use ($0.0095, ~2418J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.6% |
| Quality/$ | 121 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 439 |
| Cyclomatic complexity | 42.0 |
| Code quality | 0.228 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.513** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,434 |
| Completion tokens | 5,276 |
| Reasoning tokens | 1,128 |
| **Total tokens** | **14,838** |
| Thinking ratio | 7.6% |
| Output efficiency | 35.6% |
| Input cost | $0.002277 |
| Output cost | $0.005804 |
| Reasoning cost | $0.000158 |
| **Total cost** | **$0.009515** |
| **Total energy** | **~2418 J** |
| Solution density | 0.029586 LOC/tok |
| Correctness/$ | 121 |
| Quality/J | 0.000212 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0095  |  **Energy:** ~2418J  |  **Thinking:** 8%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 11 |
| Total lines | 439 |
| Functions | 77 |
| Classes | 16 |
| Functions/file | 7.0 |
| Classes/file | 1.5 |
| Avg lines/file | 40 |
| Type hints | 86% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 44 |
| Decorators | 1 |
| Test files | 1 |
| Test file rate | 9% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_batch_twitter_timeline_natural/session.jsonl)

*No code output — this session was narration-only.*