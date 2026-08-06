# Game Report: exp_qu6tc1zc-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:52:27

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.705

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.52) with moderate resource use ($0.9408, ~2708J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 562 |
| Cyclomatic complexity | 72.0 |
| Code quality | 0.178 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.519** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 14 |
| Completion tokens | 11,767 |
| Reasoning tokens | 0 |
| **Total tokens** | **11,781** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$0.940768** |
| **Total energy** | **~2708 J** |
| Solution density | 0.047704 LOC/tok |
| Correctness/$ | 62 |
| Quality/J | 0.000192 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.9408  |  **Energy:** ~2708J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_qu6tc1zc/session.jsonl)
- [Generated code](./exp_qu6tc1zc/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 549 |
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
