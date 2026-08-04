# Game Report: standardized_test-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [standardized_test] deepseek...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:53:23

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.804

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.63) with moderate resource use ($0.0091, ~2196J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.276 |
| Architecture div | 0.000 |
| Structure div | 0.250 |
| Thinking ratio | 4.6% |
| Quality/$ | 122 |
| Quality/J | 0.0005 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 369 |
| Cyclomatic complexity | 41.0 |
| Code quality | 0.271 |
| Novelty vs baseline | 0.669 |
| **Composite** | **0.633** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,225 |
| Completion tokens | 5,339 |
| Reasoning tokens | 660 |
| **Total tokens** | **14,224** |
| Thinking ratio | 4.6% |
| Output efficiency | 37.5% |
| Input cost | $0.002221 |
| Output cost | $0.005873 |
| Reasoning cost | $0.000092 |
| **Total cost** | **$0.009128** |
| **Total energy** | **~2196 J** |
| Solution density | 0.025942 LOC/tok |
| Correctness/$ | 122 |
| Quality/J | 0.000288 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0091  |  **Energy:** ~2196J  |  **Thinking:** 5%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines | 369 |
| Functions | 49 |
| Classes | 9 |
| Functions/file | 7.0 |
| Classes/file | 1.3 |
| Avg lines/file | 53 |
| Type hints | 35% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 27 |
| Decorators | 7 |
| Test files | 1 |
| Test file rate | 14% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_j5rhhp06/session.jsonl)

*No code output — this session was narration-only.*