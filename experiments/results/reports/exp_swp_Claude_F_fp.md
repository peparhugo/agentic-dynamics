# Game Report: perturbed-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [silent_sweep:perturbed:forced] Claude_Fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:59

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.66) with moderate resource use ($0.3609, ~690J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 303 |
| Quality/J | 0.0015 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 230 |
| Cyclomatic complexity | 24.0 |
| Code quality | 0.535 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.661** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10 |
| Completion tokens | 2,995 |
| Reasoning tokens | 0 |
| **Total tokens** | **3,005** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.7% |
| Input cost | $0.000003 |
| Output cost | $0.003295 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.360892** |
| **Total energy** | **~690 J** |
| Solution density | 0.076539 LOC/tok |
| Correctness/$ | 303 |
| Quality/J | 0.000958 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3609  |  **Energy:** ~690J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines | 230 |
| Functions | 26 |
| Classes | 11 |
| Functions/file | 4.3 |
| Classes/file | 1.8 |
| Avg lines/file | 38 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 23 |
| Decorators | 5 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_swp_Claude_F_fp/session.jsonl)

*No code output — this session was narration-only.*