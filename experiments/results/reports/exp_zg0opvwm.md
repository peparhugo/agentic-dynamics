# Game Report: baseline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:baseline:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T03:10:45

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.761

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.62) with moderate resource use ($0.0165, ~4053J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 6.8% |
| Quality/$ | 66 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 885 |
| Cyclomatic complexity | 74.0 |
| Code quality | 0.113 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.619** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,204 |
| Completion tokens | 11,347 |
| Reasoning tokens | 1,505 |
| **Total tokens** | **22,056** |
| Thinking ratio | 6.8% |
| Output efficiency | 51.4% |
| Input cost | $0.002485 |
| Output cost | $0.012482 |
| Reasoning cost | $0.000211 |
| **Total cost** | **$0.016497** |
| **Total energy** | **~4053 J** |
| Solution density | 0.040125 LOC/tok |
| Correctness/$ | 66 |
| Quality/J | 0.000153 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0165  |  **Energy:** ~4053J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 18 |
| Total lines | 885 |
| Functions | 91 |
| Classes | 8 |
| Functions/file | 5.1 |
| Classes/file | 0.4 |
| Avg lines/file | 49 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 46 |
| Decorators | 32 |
| Test files | 6 |
| Test file rate | 33% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_zg0opvwm/session.jsonl)

*No code output — this session was narration-only.*