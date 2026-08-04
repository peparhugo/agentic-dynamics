# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5_r1] cd_claude_2rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:47:19

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.818

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.76) with moderate resource use ($0.9876, ~2689J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.366 |
| Architecture div | 0.200 |
| Structure div | 0.164 |
| Thinking ratio | 0.0% |
| Quality/$ | 78 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 86% (6/7 constraints) |
| Lines of code | 562 |
| Cyclomatic complexity | 96.0 |
| Code quality | 0.178 |
| Novelty vs baseline | 0.790 |
| **Composite** | **0.761** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 20 |
| Completion tokens | 11,684 |
| Reasoning tokens | 0 |
| **Total tokens** | **11,704** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000005 |
| Output cost | $0.012852 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.987632** |
| **Total energy** | **~2689 J** |
| Solution density | 0.048018 LOC/tok |
| Correctness/$ | 78 |
| Quality/J | 0.000283 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.9876  |  **Energy:** ~2689J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 12 |
| Total lines | 562 |
| Functions | 44 |
| Classes | 11 |
| Functions/file | 3.7 |
| Classes/file | 0.9 |
| Avg lines/file | 47 |
| Type hints | 26% |
| Docstrings | 7% |
| Error handlers | 7 |
| Imports | 46 |
| Decorators | 21 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
