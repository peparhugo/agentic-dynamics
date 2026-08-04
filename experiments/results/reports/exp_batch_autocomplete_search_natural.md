# Game Report: autocomplete_search-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:autocomplete_search:baseline] ds_natural...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:49:15

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.743

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.48) with moderate resource use ($0.0180, ~5350J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 16.1% |
| Quality/$ | 59 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 1186 |
| Cyclomatic complexity | 191.0 |
| Code quality | 0.084 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.485** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 6,438 |
| Completion tokens | 13,278 |
| Reasoning tokens | 3,790 |
| **Total tokens** | **23,506** |
| Thinking ratio | 16.1% |
| Output efficiency | 56.5% |
| Input cost | $0.001738 |
| Output cost | $0.014606 |
| Reasoning cost | $0.000531 |
| **Total cost** | **$0.017999** |
| **Total energy** | **~5350 J** |
| Solution density | 0.050455 LOC/tok |
| Correctness/$ | 59 |
| Quality/J | 0.000091 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0180  |  **Energy:** ~5350J  |  **Thinking:** 16%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 12 |
| Total lines | 1186 |
| Functions | 92 |
| Classes | 10 |
| Functions/file | 7.7 |
| Classes/file | 0.8 |
| Avg lines/file | 99 |
| Type hints | 6% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 27 |
| Decorators | 9 |
| Test files | 5 |
| Test file rate | 42% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_batch_autocomplete_search_natural/session.jsonl)

*No code output — this session was narration-only.*