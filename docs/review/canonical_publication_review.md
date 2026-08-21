# Canonical-Publication Closure Review — external critique (2026-08-21)

**Provenance [X]:** operator-provided external review of main at `ec66947d5` (the merged
semantic-integrity release), received 2026-08-21. Retained as the citable input for the
canonical-publication closure patch. All load-bearing claims re-verified against the tree
before authoring the spec (verification marks in square brackets).

## Verdict

Substantially better. Architecture, package boundaries, agent-context design, and direction are
signed off. The repository is **a well-structured research operating system that is close to
having a canonical publication and control-state architecture, but still has one important
parallel data path and several contract-strengthening issues.** Recorded results: 1,505 tests,
174 guard tests, 79/79 specs compiling, successful containerized core reproduction.

| Area | Assessment |
|---|---|
| Repository architecture | 9/10 |
| Package boundaries | 9/10 |
| Agent/developer context | 9/10 |
| Reproduction architecture | 8.5/10 |
| Scientific lineage | 7/10 |
| CAP readiness | 8.5/10 |
| Overall | 8.5/10 |

Signoffs: architecture YES · refactor YES · agent-context YES · CAP structural readiness YES ·
**semantic-integrity NOT YET.**

## What is now genuinely fixed

- The lab manifest (canonical/quarantined/publication-eligible/reproduce-default/external-service)
  with named metric-definition versions; the quadrant chart renamed and quarantined; `lab_grit.py`
  implements the formal G(s) with Wilson intervals, exclusion-not-imputation, under-support
  suppression, and the honest two-level caveat.
- The semantic context guard checks `agent_config/**` for real paths, imports, CLI commands,
  scripts, retired imports/taxonomy, and drift-prone counts.
- Reproduction split into core / `--with-neo4j` / `--with-sonar`, lab set derived from the
  manifest, CI executes the container entrypoint and verifies `data.js` production.
- CAP has physically present reserved homes.

## P0 — The labs use the canonical resolver, but the website's primary story pipeline still does not

The lab path is canonical (`canonical_corpus` resolver → contract-bearing labs → publication
gate → `data.js`), but the primary story/model/review/analysis sections still flow through:

```
stories/*.json → sync_data.py → sessions.parquet / stories.parquet
    → compute_story_models() / _load_story_data() → data.js
reviews/*.json → _load_review_data() → data.js
analysis/*.json → _load_analysis_data() → data.js
```

`sync_data.py` iterates every top-level `stories/*.json` directly — no registry selection, no
central no-op condition correction. [verified: `scripts/sync_data.py:24,140` globs the raw dir;
`build_data.py:1112-1115,1270-1272` reads the parquet as "source of truth"; `:768,:892` glob raw
review/analysis dirs]

**An actual contradiction in the committed public dataset** — the canonical lab reports
`clean 135 / early_degrade 80`, but the raw-Parquet story section reports `bad_seed 41 /
early_degrade 91` (= 80 real + 11 old no-ops; bad_seed 41 = the relabeled no-ops). The same
`data.js` carries both canonical and legacy condition semantics. [verified: `data.js`
`stories.conditions` = bad_seed 41, clean 83, early_degrade 91]

**Required correction:** `build_data.py` loads one complete canonical input
(`load_canonical_tables("story","finding","review","analysis")`); `sync_data` receives
registry-selected payloads; `compute_story_models` / `_load_story_data` / `_load_review_data` /
`_load_analysis_data` consume the canonical tables; one global publication contract on `data.js`;
a guard rejects any public-data producer that directly globs `experiments/results/{stories,
reviews,analysis}` outside the resolver. A focused data-path repair, not a refactor.

## P1 — The lab contract validates freshness, but not semantic identity

`validate_contract` checks presence/non-emptiness + `input_manifest_sha256` equality only. It
does not compare `lab`, `input_dataset_id`, `registry_version`, `metric_definition_version`,
`data_integrity_policy`, `requires_external_service`, `contract_version` against the manifest
entry. Concrete mismatch: the manifest declares `grit/v1`, the committed `lab_grit.json` embeds
`grit/v0` — accepted and published because the hash matches. [verified]

**Required correction:** `validate_contract(payload, manifest_entry=…, current_identity=…)` with
exact equality on every manifest-authored semantic field; no automatic `<lab>/v0` fallback; fail
if no manifest entry, version differs, service declaration differs, lab name differs, or policy
differs. Mutation tests that independently alter every contract field and prove rejection.
Regenerate `lab_grit.json` + `data.js`.

## P1 — Resolver completeness is not measured or enforced

225 current story rows vs 215 resolved payloads (10 silently skipped by `continue` on missing/
unreadable payloads). [verified: 10 payload-less rows confirmed earlier]

**Required correction:** a `ResolutionReport` (`expected_current`, `resolved`, `missing`,
`unreadable`, `ambiguous`, `duplicate`); publication **fails closed** on an unresolved current row
unless an explicit reason-bearing waiver exists. The website distinguishes
`registry_current_records` / `resolved_measurement_payloads` / `eligible_records` / `records_used`
instead of calling everything "canonical stories".

## P2 — `n_input_records` does not mean records used

Grit resolves 279 records (64 findings + 215 stories) but uses 144 eligible cells; the contract
reports `n_input_records: 279` and the guard enforces it. [verified] Replace with
`n_resolved_records` / `n_eligible_records` / `n_used_records` / `n_excluded_records` +
optional `exclusions` breakdown (e.g. `missing_strength: 135`).

## P2 — The registry hash does not attest to exact payload content

`input_manifest_sha256` hashes `schema_version` + the registry array (correctly avoiding the
circular-manifest problem), so payload bytes can change without invalidating contracts. Rename to
`registry_identity_sha256` and add `resolved_input_sha256` over a stable sorted sequence of
`(table, canonical entity id, knowledge id, payload content digest)`.

## Smaller remaining issues

- **Test-count fields conflate scopes** — public model records show e.g. `tests_total: 1767` vs
  `tests_passed: 3290 / tests_run: 3292` (story-level peak vs summed session executions). Rename to
  `final_tests_discovered`, `test_executions_passed`, `test_executions_run`; state the pass rate is
  weighted over repeated session-level executions.
- **README figures unreconciled** — README says 1,097 sessions / 36 configs / $288.69; the
  committed dataset says 1,067 / 35 / $309.17. Either generate README figures from a canonical
  public-statistics artifact or label scopes explicitly.
- **Docker persistence overstates** — the example mounts results + apps/website, but the
  regenerated manifest writes to `/app/experiments/data_manifest.json` outside the mounts and
  vanishes under `--rm`; CI verifies data.js persistence, not the manifest.

## CAP sequencing endorsement

After this closure: I0 (CanonicalFact + predicate registry), I1 (spec-lifecycle reducer),
I2 (attempt/job reducers), I3 (workflow/policy reducers), I4 (read-only Context Compiler) can
proceed with confidence. I6 (controller) and I7 (real actuation) stay in shadow mode until fact
resolution, conflict handling, missing-state behavior, and decision calibration are observed
under real workloads.

## Bottom line

One narrowly scoped canonical-publication closure patch: (1) route story/review/analysis
publication through `CanonicalTables`; (2) resolution completeness + payload-content identities;
(3) strengthen lab-contract validation against the manifest entry; (4) regenerate Grit + all
public artifacts; (5) clarify record-count and test-count scopes; (6) generate or reconcile the
README statistics. After that, semantic-integrity signoff: YES.
