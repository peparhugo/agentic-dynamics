# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5_r2] cd_claude_2rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:55:48

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.710

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.66) with moderate resource use ($0.9114, ~2430J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.430 |
| Architecture div | 0.400 |
| Structure div | 0.130 |
| Thinking ratio | 0.0% |
| Quality/$ | 86 |
| Quality/J | 0.0004 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 440 |
| Cyclomatic complexity | 62.0 |
| Code quality | 0.227 |
| Novelty vs baseline | 0.769 |
| **Composite** | **0.663** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 16 |
| Completion tokens | 10,561 |
| Reasoning tokens | 0 |
| **Total tokens** | **10,577** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000004 |
| Output cost | $0.011617 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.911432** |
| **Total energy** | **~2430 J** |
| Solution density | 0.041600 LOC/tok |
| Correctness/$ | 60 |
| Quality/J | 0.000273 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.9114  |  **Energy:** ~2430J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines | 440 |
| Functions | 37 |
| Classes | 13 |
| Functions/file | 2.8 |
| Classes/file | 1.0 |
| Avg lines/file | 34 |
| Type hints | 46% |
| Docstrings | 3% |
| Error handlers | 6 |
| Imports | 44 |
| Decorators | 28 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 10,561 |
| Python files | 13 |
| Non-Python files | 0 |
| Code density | 0.0417 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |


---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_pt6mynpf/session.jsonl)

*No code output — this session was narration-only.*