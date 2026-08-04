# Game Report: fastapi_maintenance-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:fastapi_maintenance:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:51:12

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.759

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.65) with moderate resource use ($0.0303, ~6524J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 8.0% |
| Quality/$ | 57 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 3021 |
| Cyclomatic complexity | 153.0 |
| Code quality | 0.033 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.646** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 43,352 |
| Completion tokens | 4,756 |
| Reasoning tokens | 4,174 |
| **Total tokens** | **52,282** |
| Thinking ratio | 8.0% |
| Output efficiency | 9.1% |
| Input cost | $0.011705 |
| Output cost | $0.005232 |
| Reasoning cost | $0.000584 |
| **Total cost** | **$0.030303** |
| **Total energy** | **~6524 J** |
| Solution density | 0.057783 LOC/tok |
| Correctness/$ | 57 |
| Quality/J | 0.000099 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0303  |  **Energy:** ~6524J  |  **Thinking:** 8%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1136 |
| Total lines | 96299 |
| Functions | 3986 |
| Classes | 692 |
| Functions/file | 3.5 |
| Classes/file | 0.6 |
| Avg lines/file | 85 |
| Type hints | 42% |
| Docstrings | 3% |
| Error handlers | 98 |
| Imports | 3548 |
| Decorators | 1456 |
| Test files | 511 |
| Test file rate | 45% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_batch_fastapi_maintenance_natural/session.jsonl)

*No code output — this session was narration-only.*