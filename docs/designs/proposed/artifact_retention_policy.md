---
status: proposed
---
# Artifact Retention Policy — main vs content-addressed artifact release

Status: proposed · Date: 2026-08-28 · Source: external review **P2** —
"repository artifact governance is now the main scaling problem" · Owner: AI
FinOps Dynamics instrument. This document changes the PHYSICAL retention model
only; the logical append-only model of the corpus (ledger, registry chain,
content-addressed records) is untouched. No data is moved, deleted, or
re-packaged by this document — `scripts/bundle_artifacts.py` is the planner;
activation is a separate, operator-signed step.

## 1. The measured problem (2026-08-28, `main` @ 24e5864c2)

The corpus lives under `experiments/results/` (1.2 GB on disk) plus the git
object store (774 MB). Measured breakdown by top-level subdirectory:

| Directory / file | Size (du -sh) | Files | What it is |
|---|---|---|---|
| `workflows/` | 895 MB | 176 | workflow run ledgers + per-spec campaign payloads |
| `reports/` | 129 MB | 9,669 | game reports + embedded generated code (`exp_*` dirs) |
| `stories/` | 79 MB | 1,121 | per-story result JSONs + `transcripts/` + `logs/` |
| `kb/` | 69 MB | 16,793 | content-addressed knowledge records (`<sha256>.json`) |
| `registry_index.jsonl` | 22 MB | 34,613 rows | the canonical registry index (append-only consumer output) |
| `reviews/` | 9.2 MB | 1,533 | per-session commit/story reviews |
| `artifacts/` | 8.3 MB | 658 | backfilled generated code |
| `analysis/` | 4.3 MB | 243 | AST/Sonar/LSP post-hoc analysis |
| `cap_*` campaign dirs | ~2.5 MB | ~330 | campaign cells, proposals, scores (cap_2a…cap_adaptive_2c, etc.) |
| top-level JSONs (`.json` summaries, `lab_*.json`, `_results_summary.json`) | ~7 MB | ~40 | canonical summaries + current campaign outputs |

Age distribution (file mtime): oldest **2026-08-10 02:20**
(`reports/exp_05ngi4l9`), newest **2026-08-28 02:01** (`stories/logs/`,
the in-flight cross-model campaign). The repo on disk: working tree **2.1 GB**
(`du -sh .`), `.git` **774 MB** (`git count-objects -vH`: 2,767 loose objects
= 136.29 MiB; 170,777 in-pack objects in 38 packs = 374.04 MiB).

**The kb/ retention line (the load-bearing number).** 16,793 records on disk;
referenced by the current registry index (`registry_index.jsonl`: 13,426
unique `knowledge_id`s across 34,613 rows) = **13,416**; referenced by the
current manifest registry array (`experiments/data_manifest.json`: 12,808
rows — 12,721 `current` + 87 `tombstoned`) = **12,798**; union-referenced by
either = **13,416**. Unreferenced by BOTH = **3,377 records, 4.4 MB total**.
Age of the unreferenced set (mtime): 1,459 younger than 7 days (in-flight),
1,918 in the 7–30 day band (median 11.9 days, max 12.0) — i.e. every
unreferenced record postdates the 2026-08-24 registry rebuild, so the
bundle-candidate population is currently small and grows as producers
re-run and the registry advances past them. Lifecycle split of the registry
chain: `current` 33,628 / `superseded` 898 / `tombstoned` 87 (registry index);
the manifest collapses chains to current + tombstoned only.

**mtime caveat for kb/.** 14,110 of 16,793 kb files carry an mtime within the
last 7 days: batch producers (`kb_produce*.py`) rewrite records **in place**
on re-ingestion, so mtime is *not* creation time for kb. The age signal used
for the in-flight window is therefore mtime (conservative — re-ingested
records count as fresh), and the retention line is the **reference check**,
not the age check. The true age of a record lives in its `observed_at` /
`indexed_at` fields.

The scaling problem in one sentence: the repository carries ~1.2 GB of
historical payload whose *identity* (hashes, registry rows, summaries) is
what the research actually consumes, while the payload itself is only needed
for reproduction and forensic re-derivation.

## 2. Two-tier retention model (the review's framing)

The review's recommendation, adopted here as policy: **keep the logical
append-only model; change the physical retention model.**

- **Tier 1 — `main`:** everything the current information plane needs —
  manifests, identities, hashes, canonical summaries, current experiment
  inputs, current release fixtures, and the registry index.
- **Tier 2 — the artifact release:** historical per-record JSON, raw
  execution payloads, screenshots, superseded proposal artifacts, and large
  campaign bundles — content-addressed, reproducible through a committed
  manifest, re-hydratable on demand.

Nothing is deleted in the logical sense: Tier-2 material leaves the working
tree *only after* a committed manifest proves the bundle holds every member
byte-for-byte (sha256), so the release is reproducible from the repository
alone.

## 3. What stays in `main` (Tier 1)

- **Manifests:** `experiments/data_manifest.json` (files arrays +
  registry), any future bundle manifests (see §5), `generate_manifest.py`
  outputs.
- **Identities and hashes:** the registry index
  (`experiments/results/registry_index.jsonl` — the retention line's own
  source of truth), all sha256 identities, `source_uri` pointers.
- **Canonical summaries:** `_results_summary.json` (+ `.pre_sonar` twin),
  `_trajectory_summary.json`, `_trajectory_aggregate.json`, `verified_tests.json`,
  `lab_*.json` outputs, `evidence_integrity_*.md`, `evidence_prereq_*`,
  `session_routing_retrospective.json`, campaign score JSONs
  (`cap_*_score_*.json`, `cap_grit_grid_ledger.json`, `cap_grit_grid_metrics.json`).
- **Current experiment inputs:** `experiments/inventory.json`,
  `experiments/definitions/`, `workflows/**` specs, `experiments/specs/`.
- **Current release fixtures:** `apps/website/data.js` and everything the
  website build consumes.
- **The registry index** `experiments/results/registry_index.jsonl` — the
  append-only canonical index; never a bundle candidate.

The `data_manifest.json` `files` array already enumerates the pinned
canonical set (measured): `canonical_inputs` = `experiments/inventory.json`
(1,020,217 B) + `_trajectory_aggregate.json` (23,725 B); `canonical_outputs`
= `data.js` (188,969 B); `historical_artifacts` = `_results_summary.json`
(472,535 B). That array is a second reference source for the bundle planner
(§9): anything it names is not a candidate.

## 4. What moves to the artifact bundle (Tier 2)

- **Historical per-record kb JSON:** `experiments/results/kb/<sha256>.json`
  records unreferenced by the current registry index AND the current
  manifest (the 3,377-measured class; §1).
- **Raw execution payloads:** `reports/` game reports with embedded
  generated code (`exp_*` dirs — 9,669 files), `stories/` per-session
  transcripts and result JSONs (1,121 files), `artifacts/` backfilled code
  (658), `analysis/` post-hoc files (243), `reviews/` per-session review
  files (1,533).
- **Screenshots / large bundles:** any future `*.png`, `*.zip`, model
  output bundles that land under the eligible roots.
- **Superseded proposal artifacts:** historical `cap_*/proposals/` and
  `cap_*/cells/` payloads from campaigns the registry no longer serves
  (current campaign cells stay; §6).
- **Workflow ledgers:** `workflows/<spec>/` run ledgers are candidates in
  policy, but are **protected outright while a campaign is in flight**
  (§6) — the 2d campaign writes them now.

## 5. Bundle format (content-addressed, reproducible)

One bundle = one gzipped tar + one committed manifest.

- **Tar:** `artifacts_<bundle_sha256>.tar.gz` — members stored at their
  repository-relative paths, so re-hydration restores the exact tree layout.
- **Manifest:** `bundle_<bundle_sha256>.manifest.json`, schema
  `artifact-bundle-manifest/v1`:
  ```json
  {
    "schema_version": "artifact-bundle-manifest/v1",
    "bundle_sha256": "<sha256 of the canonical manifest JSON>",
    "generated_at": "...", "git_commit": "<HEAD>",
    "member_count": N, "total_bytes": N,
    "members": {"experiments/results/kb/<id>.json": "<sha256>", ...}
  }
  ```
- **Reproducibility:** the committed manifest enumerates every member's
  sha256. Given the manifest, the bundle is re-built and verified without
  any external state — the committed manifest is what makes the release
  reproducible, so nothing is lost. `bundle_sha256` names the manifest
  itself, making the manifest content-addressed too.
- **Placement:** the manifest is committed under
  `experiments/artifacts/manifests/`; the tar lives in the artifact release
  store (git is not the release medium for multi-hundred-MB payloads — the
  committed manifest is the git-side anchor).

## 6. The cut line

A file is a bundle candidate **iff** all of:

1. **Eligible root:** under `kb/`, `reports/`, `stories/`, `artifacts/`,
   `analysis/`, `reviews/`, `reviews_blind/`, `supervisor/`, `orphans/`,
   `legacy_labs/`, `proposals/`, or a top-level `cap_*` campaign dir.
   Top-level JSON summaries and the manifest/registry files are never
   candidates (Tier 1, §3).
2. **Reference-free:** the file is referenced by NEITHER
   `experiments/results/registry_index.jsonl` (kb `knowledge_id` →
   `kb/<id>.json`) NOR `experiments/data_manifest.json` (registry rows +
   all `files` arrays). For kb records this is the superseded-chain
   terminal: a `knowledge_id` absent from the current manifest is by
   construction not served by the registry, whatever its registry-index
   history.
3. **Past the in-flight window:** file mtime ≥ 7 days old (the default
   `--min-age-days`; the 2d campaign and its story workers are writing
   `stories/` right now — measured: newest files 2026-08-28 02:01).
4. **Not protected:** `experiments/results/workflows/` is never a candidate
   while campaigns write ledgers into it (the hard protection; §8).

## 7. Re-hydration path (restore)

Activation-time companion contract (script to be built when the policy is
accepted — `scripts/restore_bundle.py`):

1. `verify`: recompute each member's sha256 from the bundle tar and compare
   against the committed manifest — any mismatch aborts before any write.
2. `extract`: write members back to their repository-relative paths
   (tar layout is the tree layout).
3. `verify-tree`: re-hash the restored working-tree files against the
   manifest; report pass/fail.
4. Optional `git restore` for any member still tracked by git (the prune
   path removes working-tree copies of *untracked* payloads; tracked
   members are restored from git history).

Restore is a working-tree operation: the registry index and manifests never
enter the bundle (§8, invariant 1), so the information plane keeps working
during and after re-hydration.

## 8. Safety invariants (hard, enforced by `bundle_artifacts.py`)

1. **Never bundle anything the current registry index references** — the
   reference check runs at plan time AND is re-run by `--prune` at removal
   time (the registry may have advanced between plan and prune).
2. **Never bundle in-flight campaign dirs** — files younger than
   `--min-age-days` (default 7) are skipped; `workflows/` is protected
   outright (the 2d campaign writes its ledgers there now).
3. **The bundle manifest is committed before the bundle is removed from the
   working tree** — `--prune` refuses unless a verified manifest exists
   (member hashes checked against the tar), the reference check passes, and
   the age gate passes; the operator commits the manifest, then prunes.
4. **Dry-run is the default** — no flags ⇒ nothing moves, nothing is
   written; `--bundle-out` writes the tar + manifest but still removes
   nothing; `--prune` is the only removing mode and is operator-only.

## 9. Tooling: `scripts/bundle_artifacts.py`

Maintained-class planner CLI (registered in `scripts/CONTEXT.md`, CLI leaf
`agentic-dynamics data bundle`):

- `--dry-run` (default): prints each candidate's path, size, sha256, age and
  reference-check verdict, plus a summary (candidate count + bytes).
- `--bundle-out <dir>`: writes the content-addressed tar + committed-manifest
  JSON (member → sha256); removes nothing.
- `--prune`: removes bundled members from the working tree, re-verifying the
  manifest hashes, the reference check, and the age gate first. Implemented,
  never run by default; activation is an operator-signed step.
- Reference check sources: `experiments/results/registry_index.jsonl`
  (`knowledge_id` → `kb/<id>.json`) and `experiments/data_manifest.json`
  (registry rows + every `files` array path).
- Never-touch protections: `workflows/`, the two reference sources
  themselves, and the Tier-1 top-level files (§3).

## 10. Rollout / open items

- **Plan phase (this document + dry-run inventory):** no data touched. The
  measured dry-run (2026-08-28) reports the candidate population; expected
  first-wave: the ≥7-day unreferenced kb records plus the pre-campaign
  `reports/`/`stories/`/`artifacts/` payloads.
- **Activation:** operator accepts the policy, commits this doc + the first
  bundle manifest, moves the tar to the artifact release store, then runs
  `--prune` once — with the 2d campaign still in flight, the in-flight gate
  naturally excludes everything it is writing.
- **Open items:** (1) `inventory.json` as a third reference source (it
  already names report files; the planner currently trusts the two mandated
  sources only); (2) kb true-age signal via `observed_at`/`indexed_at`
  instead of mtime; (3) `restore_bundle.py` (contract in §7); (4) a bundle
  registry entry in `data_manifest.json` so the manifest references the
  bundle manifests themselves.
