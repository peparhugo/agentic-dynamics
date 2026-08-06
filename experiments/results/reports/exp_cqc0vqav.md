# Game Report: url_shortener-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** URL shortener: collision-resistance & analytics...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:50:33

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.701

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.69) with moderate resource use ($0.0098, ~2194J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 3.4% |
| Quality/$ | 121 |
| Quality/J | 0.0005 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 67% (4/6 constraints) |
| Lines of code | 146 |
| Cyclomatic complexity | 19.0 |
| Code quality | 0.683 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.692** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,910 |
| Completion tokens | 5,032 |
| Reasoning tokens | 518 |
| **Total tokens** | **15,460** |
| Thinking ratio | 3.4% |
| Output efficiency | 32.5% |
| Input cost | $0.002676 |
| Output cost | $0.005535 |
| Reasoning cost | $0.000073 |
| **Total cost** | **$0.009798** |
| **Total energy** | **~2194 J** |
| Solution density | 0.009444 LOC/tok |
| Correctness/$ | 97 |
| Quality/J | 0.000315 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0098  |  **Energy:** ~2194J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_cqc0vqav/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| JS files | 4 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 142 |
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
