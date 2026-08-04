# Game Report: baseline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:baseline:natural] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:52:08

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.763

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.58) with moderate resource use ($0.0156, ~3882J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.8% |
| Quality/$ | 68 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 838 |
| Cyclomatic complexity | 55.0 |
| Code quality | 0.119 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.577** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,979 |
| Completion tokens | 10,788 |
| Reasoning tokens | 1,282 |
| **Total tokens** | **22,049** |
| Thinking ratio | 5.8% |
| Output efficiency | 48.9% |
| Input cost | $0.002694 |
| Output cost | $0.011867 |
| Reasoning cost | $0.000179 |
| **Total cost** | **$0.015632** |
| **Total energy** | **~3882 J** |
| Solution density | 0.038006 LOC/tok |
| Correctness/$ | 68 |
| Quality/J | 0.000149 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0156  |  **Energy:** ~3882J  |  **Thinking:** 6%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 23 |
| Total lines | 838 |
| Functions | 70 |
| Classes | 11 |
| Functions/file | 3.0 |
| Classes/file | 0.5 |
| Avg lines/file | 36 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 11 |
| Imports | 62 |
| Decorators | 34 |
| Test files | 4 |
| Test file rate | 17% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_eyt9cssv/session.jsonl)

*No code output — this session was narration-only.*