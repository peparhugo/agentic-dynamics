# Game Report: std_final-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [std_final] deepseek...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:53:10

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.791

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.63) with moderate resource use ($0.0149, ~3590J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.368 |
| Architecture div | 0.250 |
| Structure div | 0.200 |
| Thinking ratio | 6.6% |
| Quality/$ | 83 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 415 |
| Cyclomatic complexity | 40.0 |
| Code quality | 0.241 |
| Novelty vs baseline | 0.694 |
| **Composite** | **0.631** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 15,452 |
| Completion tokens | 6,979 |
| Reasoning tokens | 1,592 |
| **Total tokens** | **24,023** |
| Thinking ratio | 6.6% |
| Output efficiency | 29.1% |
| Input cost | $0.004172 |
| Output cost | $0.007677 |
| Reasoning cost | $0.000223 |
| **Total cost** | **$0.014930** |
| **Total energy** | **~3590 J** |
| Solution density | 0.017275 LOC/tok |
| Correctness/$ | 83 |
| Quality/J | 0.000176 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0149  |  **Energy:** ~3590J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines | 415 |
| Functions | 8 |
| Classes | 12 |
| Functions/file | 1.0 |
| Classes/file | 1.5 |
| Avg lines/file | 52 |
| Type hints | 19% |
| Docstrings | 12% |
| Error handlers | 8 |
| Imports | 28 |
| Decorators | 2 |
| Test files | 1 |
| Test file rate | 12% |
| Parse errors | 0 |
