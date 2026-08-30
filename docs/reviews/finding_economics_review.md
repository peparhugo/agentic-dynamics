---
status: accepted
---

# Finding-Economics Closure Review — external critique (2026-08-22)

**Provenance [X]:** operator-provided external review of main at `1ea54bbed` (the merged
measurement-contribution closure), received 2026-08-22. Retained as the citable input for the
finding-economics closure. All load-bearing claims re-verified against the tree before authoring
the spec (verification marks in square brackets).

## Verdict

The measurement-contribution release fixed nearly all prior findings: the contaminated
verification-value join (now 457 resolved / 310 eligible+used / 147 excluded, v2), story cost
coverage (72/80 degraded captured, 90%), ContributionReport-derived contracts
(quality_frontier: 371 resolved / 312 used / 59 outside population), correct tombstones
(215/215/0/0; 77 contaminated + 10 no-measurement = 87), terminal tombstone semantics, and full
branch protection (test + repro + packaging). Repository architecture 9.5/10; story-corpus
publication 9/10; CAP structural readiness 9/10.

**The remaining defect is sharply bounded: the single-task FINDING corpus still treats
uncaptured economics as measured zeroes.**

| Area | Assessment |
|---|---|
| Repository architecture | 9.5/10 |
| Story-corpus publication path | 9/10 |
| Canonical lab architecture | 8.5/10 |
| Contribution accounting | 8/10 |
| Reproduction and branch controls | 9.5/10 |
| Finding-corpus economics | 5/10 |
| CAP structural readiness | 9/10 |
| Overall | 8.5/10 |

Signoffs: architecture YES · boundaries YES · story publication YES · lab contribution counts
YES · **exact contributor attestation NOT YET** · reproduction YES · **finding-corpus economics
NO** · **public semantic consistency NOT YET** · CAP structural YES · CAP fact-authority AFTER
finding-economics closure.

## P0 — The public finding corpus treats uncaptured cost/energy as real zeroes

`build_data.py:128` `_finding_entry_from_run` still normalizes [verified]:

```
:138  cost = float(run.get("cost_usd") or 0.0)
:154  thinking_ratio = float(run.get("thinking_ratio") or 0.0)
:155  escape = float(run.get("escape_score") or 0.0)
:156  architecture_divergence = float(... or 0.0)
:157  composite_score = float(... or 0.0)
:158  energy_total_j = float(run.get("energy_j") or 0.0)
:159  quality_per_joule = float(... or 0.0)
:149  narration_failure = False (not measured in this corpus — always False)
```

Then `:443-449,:492-493` aggregate and publish `correctness_per_dollar` and
`avg_quality_per_joule`; `correctness_per_dollar = correctness / max(cost, 1e-9)` turns an
uncaptured cost into an enormous positive economic score. The published `data.js` carries the
concrete case [verified]:

```
anthropic/claude-haiku-4-5  correctness_per_dollar 857,142,857.60  avg_quality_per_joule 68.87
Claude Sonnet 5             correctness_per_dollar 416,666,668.19  avg_quality_per_joule 32.59
```

One Claude Sonnet baseline run is `correctness 1.0 / test_executed_success true / cost 0.0 /
energy 0 / tokens 0 / exit_code -1` — an uncaptured/failed economic observation, published as a
free perfect run. Claude perturbation arms show `avg_cost 0.0, avg_tokens 0, avg_correctness
1.0`. Ten `"?"` strategy classifications remain in the public strategy distribution [verified].
These entries feed `compute_routing(entries)`, and the routing implementation defaults missing
correctness and cost to zero — so uncaptured cost can influence model-efficiency and route
recommendations.

**Why the guard missed it:** the zero-coercion guard matches the narrow pattern
`get("field", 0) or 0`; the adapter uses `float(run.get("cost_usd") or 0.0)`. The class is
declared unrepresentable while this expression variant implements it. Lesson (adopted in the
spec): guard the STRUCTURE (every producer routes optional fields through MeasurementCoverage),
not a string pattern.

**Required correction:** apply MeasurementCoverage to the finding adapter and aggregators for
cost_usd, energy_j, correctness, escape_score, architecture_divergence, composite_score,
quality_per_joule, thinking_ratio. Economic denominators: correctness/$ null unless cost
captured AND positive; quality/joule null unless energy captured AND positive; routing
efficiency unavailable unless outcome AND cost are measured. Every operator/model/class result
carries `{avg_captured_cost, cost_captured_records, total_records, cost_coverage}`. A route must
not interpret missing cost as free execution. Bump finding-corpus metric versions.

## P1 — Contribution contracts do not bind the exact contributor set

`ContributionReport.used_record_ids` is computed but `attach_contribution()` discards the IDs
and writes only aggregate counts — the artifact proves "312 records contributed" but not WHICH
312. `record_id()` returns only the registry entity ID, and an analysis payload deliberately
carries its underlying story's entity ID — so story and analysis produce the same ID; duplicates
are permitted and counted separately because `ContributionReport.of()` does not enforce
uniqueness.

**Required correction:** table-qualified record references
`story:<entity_id>:<knowledge_id>`, `analysis:<story_entity_id>:<content_digest>`,
`review:<entity_id>:<knowledge_id>`, `finding:<entity_id>:<knowledge_id>`; the contract carries
`used_record_refs_sha256`, `excluded_record_refs_sha256`, `used_unique_records`,
`used_contributions`. `ContributionReport.of()` rejects empty refs, duplicates (unless
multiplicity explicitly permitted), negative exclusion counts, unknown exclusion reasons. This
is the last step between self-reported counts and exact contribution lineage — and the CAP
fact-lineage primitive.

## P1 — sync_data --check still does not verify actual Parquet contents

The sidecar carries `sessions_rows_sha256 / stories_rows_sha256 / sync_transform_sha256 /
schema_sha256`, but `--check` recomputes expected in-memory hashes and compares them with the
sidecar; it reads the actual Parquet files only for row counts. Corrupted/modified Parquet
values with unchanged counts still pass.

**Required correction:** read the actual Parquet rows, canonicalize, and compute
`actual_sessions_rows_sha256` / `actual_stories_rows_sha256`; compare expected ↔ sidecar ↔
actual (three-way).

## P2 — Several metric definitions changed without version bumps

Correct bumps: verification_value/v2, story_arc/v2, cache_economics/v2. Still at v1 despite
material meaning changes: `condition_effects/v1` (cost missing-as-zero → captured-only),
`quality_frontier/v1` (population 371 → 312 joined + coverage-carrying optional metrics),
`story_review/v1` (missing correctness → null; captured-only cost), `verification_frontier/v1`
(captured-cost-only model cost + coverage). Bump all four to v2 — the metric version answers
"does this number mean the same thing as the previous version?", the source digest answers
"which code generated this". Both are needed.

## P2 — The generated source-tree identity is not fully transitive

The identity walks Python imports, but (1) relative imports (`from .canonical_corpus import ...`)
are not resolved against their package, so transitive dependencies can be omitted; (2) the hash
uses `path.name` + bytes, so two `__init__.py` files are indistinct. Use module-aware
relative-import resolution and hash repo-relative path + file length + file bytes.

## Overall

The story and lab paths now treat missing measurements correctly; the FINDING-to-publication
path still treats missing economics as free execution. One focused finding-economics closure:

1. Apply MeasurementCoverage to the canonical finding adapter and aggregators.
2. Make cost- and energy-based ratios nullable.
3. Make routing reject or explicitly model cost-unavailable observations.
4. Add exact contributor-set digests to lab contracts.
5. Verify actual Parquet values, not only expected hashes and counts.
6. Bump all semantically changed metric versions.
7. Regenerate labs, data.js, Parquet, manifest, and the verification report.

Signoff conditions: finding-corpus economics + exact contributor attestation + public semantic
consistency become YES; CAP fact-authority readiness follows.
