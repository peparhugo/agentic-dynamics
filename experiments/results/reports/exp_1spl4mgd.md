# Game Report: exp_1spl4mgd-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:12:57

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.57) with moderate resource use ($2.2412, ~6512J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 0 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 1327 |
| Cyclomatic complexity [C] | 131.0 |
| Code quality [H] | 0.075 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.569** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 30 |
| Completion tokens [M] | 28,304 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 313,065 |
| Cache write tokens [M] | 41,007 |
| **Total tokens** | **28,334** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000300 |
| Output cost [M] | $1.415200 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.825653 |
| **Total cost** | **$2.241153** |
| **Total energy [X]** | **~6512 J** |
| Solution density [C] | 0.046834 LOC/tok |
| Correctness/$ [C] | 1 |
| Quality/J [C] | 0.000087 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $2.2412  |  **Energy:** ~6512J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_1spl4mgd/session.jsonl)
- [Generated code](./exp_1spl4mgd/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1304 |
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
