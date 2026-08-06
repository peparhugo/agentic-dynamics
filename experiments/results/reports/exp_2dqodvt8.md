# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:42:31

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.431

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=0%, quality=0.35) with moderate resource use ($0.0040, ~884J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 1.000 |
| Architecture div | 1.000 |
| Structure div | 1.000 |
| Thinking ratio | 4.1% |
| Quality/$ | 0 |
| Quality/J | 0.0000 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 0% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 0 |
| Cyclomatic complexity | 1.0 |
| Code quality | 0.983 |
| Novelty vs baseline | 1.000 |
| **Composite** | **0.347** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 6,860 |
| Completion tokens | 791 |
| Reasoning tokens | 327 |
| **Total tokens** | **7,978** |
| Thinking ratio | 4.1% |
| Output efficiency | 9.9% |
| **Total cost** | **$0.004025** |
| **Total energy** | **~884 J** |
| Solution density | 0.000000 LOC/tok |
| Correctness/$ | 0 |
| Quality/J | 0.000392 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 0%  |  **Cost:** $0.0040  |  **Energy:** ~884J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_2dqodvt8/session.jsonl)
- [Generated code](./exp_2dqodvt8/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| Total lines (Py) | 0 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
