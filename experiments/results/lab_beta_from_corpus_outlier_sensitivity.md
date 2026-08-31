# Outlier-sensitivity analysis — `lab_beta_from_corpus` (ad-hoc, non-preregistered)

**Status: ad-hoc sensitivity finding · Date: 2026-09-01 · Author: control-room review
(operator-requested).** Complements `experiments/lab_books/lab_beta_from_corpus.md` (terra's
p2 writeup, verdict FAIL on protocol compliance) and
`experiments/results/lab_beta_from_corpus.json`. This note is NOT a preregistration change:
the preregistered estimator (OLS on log-log) stands as the protocol; this documents how much
the reported β magnitudes depend on the upper tail.

## Method

Same data, same exclusions as the lab: 14-day opencode.db session corpus, whitelisted models,
`_excluded()` rules (duration ≥ 10s, tokens ≥ 100, subagent split, container cells excluded,
ladder window excluded) — n = 1,429 kept sessions. Sensitivity battery on the pooled fit:

1. Baseline OLS (the reported estimate).
2. Tail trim: drop sessions with tokens/min > 100,000 (heavy-tail density; includes
   accounting artifacts — e.g. one session records 7,634,969 tokens over a 2-minute span
   (4.65M tpm), impossible as model output, consistent with fork/resume token double-count).
3. Winsorize top/bottom 1% of the response.
4. Rank association (Spearman ρ) — outlier-insensitive direction check.
5. Median-slope (Theil-Sen-style): fit the log-log slope through per-N-level medians —
   robust central-tendency slope.

## Results

### Throughput (β_tokens)

| Treatment | β_tokens | R² | n |
|---|---:|---:|---:|
| OLS baseline (reported) | 0.800 | 0.177 | 1,429 |
| Drop tpm > 100k | **0.299** | 0.071 | 1,246 |
| Drop tpm > 10k | −0.232 | 0.076 | 119 |
| Winsorize 1% | 0.805 | 0.190 | 1,429 |
| Spearman ρ | −0.43 (p < 1e-60) | — | 1,429 |
| Median-slope | **0.26** | — | 40 N-levels |

Influence diagnostics: 122/1,429 sessions exceed Cook's D > 4/n; 32 have |studentized
residual| > 3. The extreme-density sessions concentrate at low N (fork chains), the leverage
pattern that steepens a negative OLS slope.

### Cost (β_cost)

| Treatment | β_cost | R² | n |
|---|---:|---:|---:|
| OLS baseline (reported) | 0.154 | 0.035 | 1,429 |
| Drop top decile of $/1k tokens | **0.143** | 0.041 | 1,287 |
| Winsorize 1% | 0.154 | 0.035 | 1,429 |
| Median-slope | **0.106** | — | 40 N-levels |

## Findings

1. **The direction is robust; the magnitudes are not.** A real negative association between
   concurrency and per-session token yield survives every treatment (rank ρ = −0.43, and the
   median-slope is positive β ≈ 0.26). But the reported β_tokens = 0.80 ("severe") is inflated
   roughly 2.5–3× by the heavy upper tail of the density distribution; robust central-tendency
   estimates land at β ≈ 0.26–0.43 ("moderate").
2. **The `moderate_tax` decision is a boundary artifact.** β_cost = 0.154 clears the 0.15
   threshold by 0.004; every robust treatment (top-decile drop 0.143, median-slope 0.106) sits
   below it. Under the prereg consequence table, the robust reading implies "leases may allow
   wide fleets; ladder rerun low priority" — the opposite conclusion from the reported verdict.
3. **The measurement surface itself is suspect at the tails.** The multi-million-token
   sessions are accounting artifacts (token counters surviving across resume/forks into
   compressed durations). They belong in the controlled run's instrumentation scope: the
   ladder rerun must record per-attempt tokens from the ledger, not session-table deltas.

## Recommendation

- Report the lab with BOTH numbers: the preregistered OLS estimate (0.80 / 0.154, verdict
  moderate_tax per protocol) AND this sensitivity (robust: ~0.3 / ~0.11, verdict
  negligible-to-moderate). The controlled ladder rerun — post admission gates, per the
  prereg's own consequence table — is the arbiter; do not let either reading size the leases
  alone.
- The admission_leases lease sizing should carry the robust range, not the point estimate:
  wide fleets are dollar-cheap under either reading; the throughput tax is moderate (~0.3),
  not severe (~0.8).
- Do not silently change the lab's estimator (prereg protocol); if the robust estimator
  should become the registered one, that is a new preregistered version.

## Provenance

[C] computed from the same opencode.db session corpus + exclusion rules as
`lab_beta_from_corpus.py` (n = 1,429), battery run 2026-09-01 00:45 CEST. Fit code: ad-hoc
script, not committed as a maintained command; the tables above are the durable record.
