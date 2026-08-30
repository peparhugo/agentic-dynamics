---
status: accepted
---

# Public-Truth Closure Verification — release gate (2026-08-21)

**Provenance [C]:** operator-executed release gate for the public-truth closure patch
(phases p1–p7) driven by `docs/reviews/public_truth_review.md` (external review of `main` at
`400673f84`). Every check below was executed against the working tree at the time of writing;
the PASS/FAIL verdict per check is authoritative for this closure.

## Verdict

**Public semantic consistency signoff: PASS.** Every P0/P1/P2 and "smaller" finding in the
review is closed by a committed phase, the full suite is green, the spec corpus compiles, the
reproduction (dry-run and container) produces `data.js`, the invariants hold, and `main` is
branch-protected. The CAP extraction directive is recorded, not implemented (CAP stays frozen).

## Coverage proof — every finding → a phase → PASS

Zero orphans: each finding below maps to exactly one committed phase, and no phase is unclaimed.

| # | Finding (review section) | Phase | Commit | Status |
|---|---|---|---|---|
| 1 | P0 — static public narrative contradicts the canonical dataset (156/772/$219.51, `bad_seed` arm, 88.7% 1572/1772) | `p1_static_narrative` | `f4eafabc2` | PASS |
| 2 | P0/P1 — analysis publishes unavailable LSP as zero (`lsp_errors_per_cell: 0.0`) | `p2_null_not_zero` | `8618cdac0` | PASS |
| 3 | P1 — two incompatible cost denominators (haiku `$1.359/24` vs `$1.631/20`) | `p2_null_not_zero` | `8618cdac0` | PASS |
| 4 | P1 — record-scope contracts default to "everything was used" (457/457/457/0) | `p3_record_scopes` | `ffc413ff8` | PASS |
| 5 | P1 — ten payload-less rows permanently waived instead of retracted | `p4_tombstones_waivers` | `6339e4158` | PASS |
| 6 | P1/P2 — `resolved_input_sha256` excludes `_canonical_condition` (normalization-blind) | `p5_hash_semantics` | `8d46537cc` | PASS |
| 7 | smaller — README "By the Numbers" has figures absent from `public_statistics` | `p6_manifest_sync_readme` | `14f5d0445` | PASS |
| 8 | smaller — `sync_data --check` is a row count, not a parity check | `p6_manifest_sync_readme` | `14f5d0445` | PASS |
| 9 | smaller — `generate_manifest.py` treats the retired summary as a first-class entry | `p6_manifest_sync_readme` | `14f5d0445` | PASS |
| 10 | smaller — `main` is unprotected (no required status checks) | `p7_truth_verify` | this commit | PASS |
| — | CAP readiness note (adopt in the CAP spec, not here) | recorded below | — | RECORDED |

## Check 1 — Full suite green

```
1565 passed, 1 skipped   (0 failed, 0 deselected)
```

All guard suites green, including the static-narrative guard added in p1
(`tests/test_static_narrative_guard.py`), the publication single-door guard, the lab-contract
and record-scope guards, the stale-path guard, and the new sync/parity guards. The two staging
failures present at the start of the closure — `public_truth_review.md`'s missing `status`
frontmatter and `public_truth_closure.yaml`'s flat-dir placement — are fixed here (the review
doc now carries `status: accepted`; the closure spec moved to `workflows/repository/` with
`artifact_kind: workflow`).

## Check 2 — Compile-gate all specs

```
compile-gate: 81/81 specs valid   (6 experiments + 75 workflows)
```

Every `experiments/definitions/*.yaml` + `workflows/**/*.yaml` loads, passes
`validate_spec` (structural + artifact-identity + requires/produces gates), and compiles to a
DAG via `compile_spec`. The spec index regenerated to 81 entries after the closure spec was
re-homed.

## Check 3 — Reproduce core dry-run

`scripts/reproduce.sh --dry-run` prints the full core pipeline (inventory refresh → sync →
analyze_worktrees `--no-tests --no-sonar` → analyze_trajectories → 8 canonical labs →
build_data → generate_manifest) and executes nothing. PASS.

## Check 4 — Container core run produces data.js

`docker build -t agentic-dynamics:p7-gate .` succeeds; `docker run … agentic-dynamics:p7-gate`
runs `reproduce.sh core` to completion (**exit 0**) and writes `apps/website/data.js`.
The run surfaced (and this phase fixed) one reproduction gap: the image did not COPY
`experiments/specs/`, so the p6 spec counts (`experiment_specs`/`workflow_specs`) would read
zero in-container. The Dockerfile now copies the generated spec index; verified in-container
`_spec_counts() → {'experiment_specs': 6, 'workflow_specs': 75}`.

**Known limitation (not a defect of this closure):** `inventory.py refresh` re-reads the live
opencode database, so `db_sessions_total` (the raw session count reported separately from the
1,067 canonical story sessions) is a live snapshot, not a deterministic constant. The canonical
figures (registry-derived) are deterministic.

## Check 5 — Invariant audit

- **Redis isolation** — the framework queue lives on `FINOPS_REDIS_PORT` (default **6380**);
  `knowledge_stream.py` documents and enforces "never 6379" (the story-agent sandbox that
  `flushall()`s). Unchanged. PASS.
- **Firebase dual-host** — `apps/website/.firebaserc` still declares `ai-finops-rulebook`
  (canonical) + `agentic-dynamics` (mirror). Never retired. PASS.
- **CAP frozen** — `docs/release/consolidation/cap_freeze_note.md` records the Context Abstraction
  Plane freeze (I0–I7 paused); no CAP code was added by this closure. PASS.

## Check 6 — Branch protection

`gh` is authenticated. Required status checks enabled on `main` via the branch-protection API:
`required_status_checks.contexts = ["test"]` (the `Tests & Lint` workflow's primary job).
Verified with `gh api …/branches/main/protection`.

## CAP extraction directive (recorded, not implemented)

Per the review's CAP readiness note, the following contracts are **early forms of** generic
CAP contracts and must be extracted into the reserved `core/contracts.py` home (CAP I5) when
I0–I4 resumes — never duplicated, and leaving publication-specific filesystem joins in
`reporting/`:

- `ManifestIdentity` / `ResolvedInputIdentity` → canonical-fact identity
- `ResolutionIssue` / `ResolutionReport` → fact resolution state
- waiver policy → policy exception
- semantic contract (`lab_contract`) → provenance chain
- record-scope accounting → scope
- unknown/conflict status → unknown/conflict status

(Recorded here and carried in `docs/release/consolidation/cap_freeze_note.md`; no CAP code written.)

## Signoff

- public semantic consistency: **PASS**
- every P0/P1/P2/smaller finding → a phase → PASS: **PASS (zero orphans)**
- full suite + guard suites green: **PASS**
- spec compile-gate: **PASS (81/81)**
- reproduction (dry-run + container) → `data.js`: **PASS**
- invariant audit (Redis / Firebase / CAP): **PASS**
- branch protection on `main`: **PASS**
