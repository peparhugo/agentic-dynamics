# Measurement-Contribution Closure Review — external critique (2026-08-21)

**Provenance [X]:** operator-provided external review of main at `931eeb873` (the merged
public-truth closure), received 2026-08-21. Retained as the citable input for the
measurement-contribution closure. All load-bearing claims re-verified against the tree before
authoring the spec (verification marks in square brackets).

## Verdict

The previous review was addressed substantially and correctly: singular canonical input boundary,
semantic + payload identities, explicit record-scope contracts, global publication contract,
cost-coverage reporting, null handling for LSP, actual tombstones, corrected headlines, protected
main. **No longer a refactoring or sprawl problem.** But the "public semantic consistency: PASS"
signoff is not yet earned: one canonical published lab is demonstrably contaminated, and several
measurement-contract guarantees remain self-declared rather than reconciled against actual
contributions.

| Area | Assessment |
|---|---|
| Repository architecture | 9.5/10 |
| Canonical resolver | 9/10 |
| Reproduction architecture | 9/10 |
| Public headline consistency | 8.5/10 |
| Lab lineage infrastructure | 8.5/10 |
| Measurement semantics | 6.5/10 |
| CAP structural readiness | 9/10 |
| Overall | 8.5/10 |

Signoffs: architecture YES · refactor YES · singular boundary YES · reproduction YES · headline
figures MOSTLY · lab provenance YES · **canonical metric correctness NOT YET** · **public semantic
consistency NOT YET** · CAP structural YES · CAP fact-authority AFTER contribution closure.

## P0 — lab_verification_value publishes a contaminated correlation

The lab joins current stories to current reviews, but `stories.get(sid, ("?", 0))` [verified:
`scripts/lab_verification_value.py:75`] converts unmatched reviews into `model: "?"`, `tests: 0`
rows and keeps processing them. The published artifact contains the "?" population (432
commit-review observations, `better_rate 0.519 / worse_rate 0.074`, driving a correlation of
−0.154) [verified: "?" present in the artifact] while the contract declares 457 resolved /
457 eligible / 457 used / 0 excluded. The lab is canonical, publication-eligible, website-keyed.

**Required:** the join must fail explicitly (`review_without_current_story += 1; continue`);
identify `story_without_review`; the contract declares the actual joined population; bump
`verification_value/v1` → `verification_value/v2`; regenerate artifact + data.js; guard: no
output row has `model == "?"`, every review contributing to the correlation has a joined current
story, contract counts reconcile with the join. Until fixed, the result must not be published or
cited.

## P1 — Cost denominator policy still inconsistent across canonical outputs

Primary story condition view reports captured-cost coverage (early_degrade: 80 cells / 72
captured / 90% / $1.401), but `lab_condition_effects` does `cost = summary.get("total_cost", 0) or 0`
and averages over ALL cells ($1.261). [verified: `lab_condition_effects.py:86,109`] Same pattern
in `lab_story_review` (averages over all cells), `lab_story_arc` (inserts zero for absent session
cost), `lab_cache_economics` (excludes zeros but publishes no coverage).

**Required:** ONE shared `MeasurementCoverage` primitive
(`value: float | None, n_available: int, n_total: int, coverage: float`); cost presence explicit
via `cost_captured`, not inferred from `cost > 0`; every published cost average carries
`avg_captured_cost / total_captured_cost / cost_captured_records / total_records / cost_coverage`.

## P1 — Record-scope contracts explicit, but not proven against computation

Contract v4 forces explicit counts, but the validator only checks they add up — it does not
prove they describe the records that actually contributed. `lab_quality_frontier` resolves 215
stories + 156 analyses, builds a lookup of all 215 stories, but produces measurements only while
iterating the 156 analyses — ~59 story records are outside the effective population yet the
contract declares all 371 eligible and used. [verified pattern]

**Required:** the computation itself returns a typed `ContributionReport` (`resolved, eligible,
used, excluded, unused_eligible, exclusion_reasons, used_record_ids`); `result, contribution =
compute(...)`; the contract is ATTACHED from the contribution, never hand-authored afterwards.
Tests reconcile actual output populations with contract populations for every canonical lab.

## P1 — Static registry fallback text is already stale again

Canonical data reports 215 current / 215 resolved / 0 waived / 87 tombstoned, but
`evidence.html` still says "225 current story rows … 215 resolved … 10 waived … 77 tombstoned
(contaminated, excluded)". [verified: `apps/website/evidence.html:95`] JS replaces numeric
spans, but the semantic phrase is wrong: only 77 tombstones are contaminated; 10 are
no-measurement retractions. The static guard only blacklists retired numbers — it does not
assert fallbacks equal current public_statistics. The home page also claims "Every token,
dollar, cache hit, and test is measured" while cost coverage is incomplete.

**Required:** static fallbacks either generated from public_statistics or parsed in tests and
required to match data.js exactly; split `tombstoned_excluded` into `contaminated_tombstones: 77,
no_measurement_tombstones: 10, tombstones_total: 87`; prose reports coverage honestly.

## P2 — Null-versus-zero discipline fixed for LSP, but not generalized

`build_data.py` still does `sol.get("correctness_score", 0) or 0` and
`basin.get("escape_score", 0) or 0` [verified: `scripts/build_data.py:906,912`];
`lab_quality_frontier` defaults empty metric lists to 0.0; `lab_story_review` gives session
correctness 0.0 when no tests exist — conflating "tests ran and all failed" with "no verified
result exists". The MeasurementCoverage rule must be universal: an unavailable measurement is
null with zero coverage, never numeric zero.

## P2 — Tombstone history contains a contradictory "current" predecessor

An entity's head is tombstoned but its nested version history keeps the original version
`current` with `valid_to = null` — because the migration created the tombstone with
`supersedes = None` and compaction only marks predecessors superseded when another record
explicitly points to them. [verified: registry_index.jsonl entity `37679fe003ca` versions
`['current', 'tombstoned']`] Directly CAP-relevant: a canonical-fact system cannot have a
retracted head with an eternally-open predecessor.

**Required:** tombstones explicitly name the previous `knowledge_id` as `supersedes`, OR
compaction enforces terminal semantics (all earlier open versions become `superseded` with
`valid_to = tombstone.valid_from`).

## P2 — The publication source identity is incomplete

`generator_source_tree_identity` hashes only build_data/canonical_corpus/lab_contract/lab_manifest
— not core.constants, control.routing, measurement.solution, or the eight lab scripts, so a
routing/weight/normalization/lab-algorithm change can alter the published dataset without
changing the identity. Metric versions depend on a human remembering to bump.

**Required:** every lab contract carries `metric_source_sha256` + `metric_definition_version`;
the global contract covers all direct computation dependencies, every published lab artifact's
source identity, the policy content hash, and external static parameters — a generated
dependency manifest rather than a hand-maintained tuple.

## P2 — sync_data --check is not full parity

`--check` compares registry identity, resolved-input identity, row counts, sidecar counts — but
not row CONTENTS against recomputed rows, so an old Parquet passes when only transformation code
or field values changed. Add `sessions_rows_sha256, stories_rows_sha256, sync_transform_sha256,
schema_sha256` and recompute in `--check`.

## P3 — Branch protection covers only the `test` job

The workflow has three jobs (`test`, `repro`, `packaging`); only `test` is a required status.
`repro` and `packaging` are exactly the checks that caught missing Docker files and wheel
behavior. Require all three, or one final gate job depending on all three.

## Overall

The system can prove where records came from, but not yet which records actually contributed to
every published metric. One focused measurement-contribution closure:

1. Fix lab_verification_value (v2) and regenerate all public artifacts.
2. Centralize captured-cost + optional-measurement handling for all canonical labs.
3. Typed ContributionReport generated by each computation; contracts attached, never
   hand-authored.
4. Reconcile every canonical lab contract against actual joined/contributing records.
5. Close predecessor validity when a tombstone becomes terminal.
6. Make static HTML fallbacks exactly match generated statistics.
7. Expand source and Parquet content identities.
8. Require test, repro, and packaging on main.

Final signoff conditions: canonical metric correctness + public semantic consistency become YES
after this closure; CAP fact-authority readiness follows.
