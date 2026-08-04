# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r2] cd_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:58:14

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.796

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.64) with moderate resource use ($0.0156, ~3904J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.348 |
| Architecture div | 0.250 |
| Structure div | 0.148 |
| Thinking ratio | 3.2% |
| Quality/$ | 61 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 962 |
| Cyclomatic complexity | 92.0 |
| Code quality | 0.104 |
| Novelty vs baseline | 0.680 |
| **Composite** | **0.644** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,502 |
| Completion tokens | 12,612 |
| Reasoning tokens | 688 |
| **Total tokens** | **21,802** |
| Thinking ratio | 3.2% |
| Output efficiency | 57.8% |
| Input cost | $0.002296 |
| Output cost | $0.013873 |
| Reasoning cost | $0.000096 |
| **Total cost** | **$0.015627** |
| **Total energy** | **~3904 J** |
| Solution density | 0.044124 LOC/tok |
| Correctness/$ | 61 |
| Quality/J | 0.000165 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0156  |  **Energy:** ~3904J  |  **Thinking:** 3%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 27 |
| Total lines | 962 |
| Functions | 101 |
| Classes | 14 |
| Functions/file | 3.7 |
| Classes/file | 0.5 |
| Avg lines/file | 36 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 12 |
| Imports | 70 |
| Decorators | 75 |
| Test files | 4 |
| Test file rate | 15% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_w8ayd_ci/session.jsonl)

*No code output — this session was narration-only.*