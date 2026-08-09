# Game Report: exp_qu6tc1zc-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:39:35

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.705

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.48) with moderate resource use ($0.9408, ~2708J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 562 |
| Cyclomatic complexity [C] | 72.0 |
| Code quality [H] | 0.178 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.476** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 14 |
| Completion tokens [M] | 11,767 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 87,478 |
| Cache write tokens [M] | 21,184 |
| **Total tokens** | **11,781** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.9% |
| Input cost [M] | $0.000140 |
| Output cost [M] | $0.588350 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.352278 |
| **Total cost** | **$0.940768** |
| **Total energy [X]** | **~2708 J** |
| Solution density [C] | 0.047704 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000176 |

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
