---
status: accepted
---

# Public-Truth Closure Review — external critique (2026-08-21)

**Provenance [X]:** operator-provided external review of main at `400673f84` (the merged
canonical-publication closure), received 2026-08-21. Retained as the citable input for the
public-truth closure patch. All load-bearing claims re-verified against the tree before
authoring the spec (verification marks in square brackets).

## Verdict

The closure release fixed the central architectural problem: a singular canonical-input path,
explicit resolution accounting, stronger lab contracts, corrected condition semantics, and an
actually exercised reproduction container. The repository is now **a well-structured research
operating system with a largely credible canonical publication architecture. The remaining
problems are localized semantic-output issues, not architectural sprawl.**

| Area | Assessment |
|---|---|
| Repository architecture | 9/10 |
| Canonical publication architecture | 8.5/10 |
| Agent and developer context | 9/10 |
| Reproduction | 9/10 |
| Scientific lineage | 8/10 |
| Public-output consistency | 6.5/10 |
| CAP structural readiness | 9/10 |
| Overall | 8.5/10 |

Signoffs: architecture YES · refactor YES · singular canonical input YES · lab lineage YES ·
reproduction YES · **public semantic consistency NOT YET** · CAP structural YES ·
CAP fact-authority readiness AFTER the remaining null/waiver/hash corrections.

## What is genuinely fixed

- `canonical_corpus.py` now owns current-only filtering, story/review/analysis/finding
  resolution, canonical condition correction, registry + resolved-input content identity,
  resolution issues/reports, and fail-closed waivers. The system distinguishes
  *registered-as-current / resolved-to-payload / accepted-under-policy / used-in-result*.
- `build_data.py` loads a canonical table bundle; `sync_data.py` receives registry-selected
  records with canonical condition values. The published split is `clean 135 / early_degrade 80`.
- Lab contracts carry registry identity, resolved-input identity, metric-definition version,
  resolved/eligible/used/excluded counts, exclusion reasons, policy, external-service
  declaration; semantic validation against the manifest entry; grit/v1 corrected.
- Grit is one measured result: 279 resolved, 144 eligible and used, 135 excluded with reasons.
- Reproduction is tested as actual reproduction: container core run verifies `data.js` AND
  regenerated manifest.

## P0 — The static public narrative still contradicts the canonical dataset

`evidence.html`/`index.html` still carry static 156 stories / 772 sessions / $219.51 in page
metadata, Open Graph tags, headlines ("What 772 Agentic Sessions Reveal"), prose, and footers;
`index.html` retains "772 sessions" metadata/social text and references `bad_seed` as a live arm;
a stale "88.7% across 1572/1772 tests" claim remains. [verified extensively]
Client-side replacement cannot repair metadata, OG tags, snippets, or prose without placeholders.

**Required:** one generated `public_statistics` artifact for ALL public figures (README,
index/evidence, meta descriptions, OG tags, structured data, headlines) + a guard scanning
`apps/website/*.html` for retired corpus figures and retired active-treatment terms.

## P0/P1 — The primary analysis section still publishes unavailable signals as zero

The canonical `quality_frontier` lab publishes `lsp_errors_per_cell: null` when no language
server ran, but the primary analysis aggregation still counts `available=0` cells with zero
errors/warnings and divides by all cells — publishing 0.0. [verified: every `analysis.models`
row has `lsp_available: 0, lsp_errors_per_cell: 0.0`] The evidence page still describes live
LSP analysis and names a model with "cleanest LSP output". This converts *not measured* into
*measured and perfectly clean*.

**Required:** every optional measurement publishes `{value, n_available, n_total, coverage}`;
only available values enter the average; `n_available == 0` → `null`. No LSP-quality claims
until coverage is nonzero.

## P1 — Story cost has two incompatible denominator policies

The top-level canonical model section distinguishes cells from cost-captured cells; the
`stories.models` section defaults uncaptured cost to zero and divides by every cell, producing
a lower average for the same model. [verified: haiku `stories.models` $1.359 over 24 cells vs
top-level $1.631 over 20 captured]

**Required:** nullable cost throughout; publish `avg_captured_cost`, `cost_captured_cells`,
`total_cells`, `cost_coverage`; one denominator policy in every view.

## P1 — Record-scope contracts still default to "everything was used"

The API defaults `eligible = resolved`, `used = eligible` unless the lab overrides.
`lab_condition_effects` resolves 215 stories + 242 reviews, uses all stories but only 155
reviews in its rows, yet declares 457 eligible/used/0-excluded. [verified]

**Required:** remove permissive defaults; require explicit `n_resolved / n_eligible / n_used /
n_excluded / n_unused_eligible` + reason counts (`review_without_current_story`,
`story_without_review`, `missing_required_field`, `outside_analysis_population`). Tests
reconcile contracts against actual contribution counts.

## P1 — The ten unresolved "current" stories should be retracted, not permanently waived

225 registry-current vs 215 resolved; 10 waivers. The registry still says *current* while the
waiver says *no usable measurement*. The waiver key is broad (table + locator) — a future
different problem at the same locator could inherit an old waiver. [verified: waiver schema is
table/locator/reason-based]

**Required:** waivers as temporary operational exceptions, hard-bound to `table, logical_locator,
issue_kind, entity_id, knowledge_id, source_uri, reason, review_by/expiry`; reject stale/
duplicate/unmatched waivers. For the known ten, canonical tombstones are cleaner than permanent
exceptions.

## P1/P2 — The input hash still does not cover canonicalized semantics

`resolved_input_sha256` hashes only non-underscore payload keys, excluding `_canonical_condition`
and other derived semantic fields. A normalization-policy change leaves the hash unchanged while
the effective analysis population changes. [verified: docstring at canonical_corpus.py:186-191]

**Required:** hash an explicit canonical projection (canonical condition, resolved identity,
selected measured values, reducer/policy version, waiver-set digest). `data.js` gains a global
publication contract: registry identity, resolved-input identity, data-integrity policy version,
normalization/reducer version, waiver digest, generator source-tree identity.

## Smaller issues

- README "By the Numbers" still contains values not in `public_statistics` (provider count, spec
  counts); the guard tests only a subset.
- `sync_data --check` reports Parquet counts but is not a real parity check; an empty canonical
  source should not leave an older Parquet in place — use atomic replacement + a
  source-identity sidecar.
- `generate_manifest.py` hashes the retired `_results_summary.json` as a first-class entry and
  carries static historical limitations; distinguish `canonical_inputs / canonical_outputs /
  historical_artifacts`.
- `main` is unprotected: no required status checks.

## CAP readiness note (adopt in the CAP spec, not here)

`ManifestIdentity`, `ResolvedInputIdentity`, `ResolutionIssue`, `ResolutionReport`, waiver
policy, semantic contract, and record-scope accounting are **early forms of** canonical-fact
identity, fact resolution state, provenance chain, scope, unknown/conflict status, and policy
exception. When CAP I0–I4 begins, extract and generalize these generic contracts into the
shared boundary (`core/contracts.py`) — do not duplicate them; leave publication-specific
filesystem joins in `reporting/`.

## Bottom line

One focused public-truth closure: (1) generate all static site statistics/metadata/treatment
descriptions from canonical public statistics; (2) replace zero-as-missing in primary analysis
and cost aggregation; (3) make lab record scopes explicit and contribution-aware; (4) tombstone
the ten invalid current records and harden temporary waivers; (5) add a global publication
contract covering semantic normalization and source-tree identity; (6) protect main.
