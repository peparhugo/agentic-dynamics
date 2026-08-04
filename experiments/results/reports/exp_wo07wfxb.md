# Game Report: exp_wo07wfxb-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] constraint_detection_3rep...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T03:03:55

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.768

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.67) with moderate resource use ($0.0145, ~3437J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 3.7% |
| Quality/$ | 73 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 750 |
| Cyclomatic complexity | 55.0 |
| Code quality | 0.133 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.666** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,016 |
| Completion tokens | 9,876 |
| Reasoning tokens | 775 |
| **Total tokens** | **20,667** |
| Thinking ratio | 3.7% |
| Output efficiency | 47.8% |
| Input cost | $0.002704 |
| Output cost | $0.010864 |
| Reasoning cost | $0.000109 |
| **Total cost** | **$0.014452** |
| **Total energy** | **~3437 J** |
| Solution density | 0.036290 LOC/tok |
| Correctness/$ | 73 |
| Quality/J | 0.000194 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0145  |  **Energy:** ~3437J  |  **Thinking:** 4%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 22 |
| Total lines | 750 |
| Functions | 83 |
| Classes | 9 |
| Functions/file | 3.8 |
| Classes/file | 0.4 |
| Avg lines/file | 34 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 10 |
| Imports | 50 |
| Decorators | 30 |
| Test files | 5 |
| Test file rate | 23% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_wo07wfxb/session.jsonl)

*No code output — this session was narration-only.*