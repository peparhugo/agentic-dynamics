---
<<<<<<< HEAD
status: proposed
=======
status: accepted
>>>>>>> 9d2c3c57d
supersedes:
---

# docs_architecture_refresh — remediation plan (adversary FAIL findings)

<<<<<<< HEAD
**Status: proposed (operator-signed remediation plan).** Source: the p4 adversarial review
(`docs/reviews/docs_architecture_refresh_adversary.md`, verdict FAIL — findings recorded,
fixes deferred per the spec's contract: "remediation remains an operator decision or a
follow-up phase"). This plan is the operator's decision: every FAIL finding below is
accepted, assigned, and gated on re-verification before the branch may merge.
=======
**Status: implemented (operator-signed remediation plan) — frontmatter `accepted` per the
doc-lifecycle kind-tree contract (`docs/reviews/*` → `accepted`).** Source: the p4 adversarial review
(`docs/reviews/docs_architecture_refresh_adversary.md`, verdict FAIL — findings recorded,
fixes deferred per the spec's contract: "remediation remains an operator decision or a
follow-up phase"). This plan is the operator's decision: every FAIL finding below is
accepted, assigned, and gated on re-verification before the branch may merge. The five-point
acceptance gate has now re-run clean on the remediated branch and is recorded in
[§ Acceptance gate](#acceptance-gate-re-verification-before-merge) below.
>>>>>>> 9d2c3c57d

## Findings → remediation

### F1 — Stale anchors to the deleted proposed fleet design
- **Evidence**: the p1 audit cites `docs/designs/proposed/fleet_ladder_architecture.md` at
  `2026-09-01_docs_drift_audit.md:22,70-73,79`; `docs/fleet/00_proposal.md:11` and
  `docs/fleet/01_infra_inventory.md:9` still link the proposed design — all now unresolvable
  (the design moved to `docs/designs/implemented/`).
- **Fix**: re-point every reference to `docs/designs/implemented/fleet_ladder_architecture.md`;
  supersede the `docs/fleet/00`/`01` operational claims per the doc-lifecycle rules.
- **Severity**: medium (broken references in the very docs this workflow exists to repair).
- **Owner**: remediation phase (cheap — mechanical re-pointing).
<<<<<<< HEAD
=======
- **Closure evidence**: [C] every audit anchor re-pointed
  (`docs/architecture/current/2026-09-01_docs_drift_audit.md:22,70,71,73,79` — the proposed
  location replaced by `docs/designs/implemented/fleet_ladder_architecture.md`); [M] both
  fleet docs carry the lifecycle-supersession banner for their operational claims
  (`docs/fleet/00_proposal.md:7-12`, `docs/fleet/01_infra_inventory.md:7-11`); [M] the deleted
  proposed path appears nowhere in the branch's `docs/` (`git grep` clean — see the gate's
  check (a) evidence).
>>>>>>> 9d2c3c57d

### F2 — Untagged, unanchored claims in ARCHITECTURE.md
- **Evidence**: the module count (`ARCHITECTURE.md:46-49`, 59→107), the dependency spine
  (`:110`), and the CAP-consumption claim (`:155-182`) carry no provenance tag and no
  `file:line` anchor.
- **Fix**: add `[M]`/`[C]` tags + repository-relative anchors per the spec's hard rule 3
  ("a claim without a provenance tag or a file:line anchor is not merged"). Module count:
  anchor to `src/agentic_dynamics/` module inventory (a `[C]` glob count at a pinned SHA);
  spine: anchor to `tests/test_dependency_direction.py` + the plane `__init__` imports.
- **Severity**: high (violates the workflow's own provenance contract).
- **Owner**: remediation phase.
<<<<<<< HEAD
=======
- **Closure evidence**: [C] the module count is now `[C]`-tagged with the exact command and a
  pinned SHA (`ARCHITECTURE.md:46-49` — 107 modules at `806c0d344`, verified by re-running
  `git ls-files 'src/agentic_dynamics/**/*.py' | wc -l`); [M] the spine is `[M]`-tagged and
  anchored to the lint's tier model + the eight plane `__init__.py` import maps
  (`ARCHITECTURE.md:109-116`); [C] the CAP-consumption table now carries per-row `[C]` anchors
  to the consuming modules, the campaign specs, and the score artifacts
  (`ARCHITECTURE.md:161-194`).
>>>>>>> 9d2c3c57d

### F3 — cap_2b current-state claim contradicted by the seam
- **Evidence**: `ARCHITECTURE.md:172` states cap_2b "applies accepted proposals" while the
  application seam requires `workflow.params.control_route: true`
  (`src/agentic_dynamics/control/rules.py:12-19`) and the committed corpus has zero opt-ins
  (`tests/test_context_plane_seam.py:271-284`).
- **Fix (now)**: correct the claim — the shadow rails are proposal-only until a workflow
  opts in; the authority must say so. **Fix (follow-up)**: the opt-in itself (a workflow
  exercising the applied path) is a separate decision, not part of this remediation.
- **Severity**: high (a false current-state claim — the exact class this workflow kills).
- **Owner**: remediation phase (doc correction) / operator (opt-in decision).
<<<<<<< HEAD
=======
- **Closure evidence**: [C] the corrected claim anchors the applied path to the campaign's own
  `apply_only_in_adaptive_arm` invariant + the score artifact (3 applied cells in
  `experiments/results/cap_2b/cap_2b_score_20260826T160018Z.json`) and explicitly separates it
  from the I7 `control_route` seam, which no committed spec sets
  (`ARCHITECTURE.md:180`, `workflows/repository/cap_2b.yaml:36-37,64-66`,
  `tests/test_context_plane_seam.py:271-284`). The opt-in decision remains the operator's.
>>>>>>> 9d2c3c57d

### F4 — Fleet design overgeneralization
- **Evidence**: `docs/designs/implemented/fleet_ladder_architecture.md:27-30` claims all
  cell services process one queue job at a time, contradicted by the stream consumers,
  long-running daemons, and batch producers in `infrastructure/docker-compose.ladder.yml:167-257`.
- **Fix**: scope the claim to the story pool (the queue workers); describe the stream
  consumers/daemons as long-running units.
- **Severity**: medium (wrong architecture description in the new authority doc).
- **Owner**: remediation phase.
<<<<<<< HEAD
=======
- **Closure evidence**: [M] the design now scopes "one queue job at a time" to the
  story/analysis/review BRPOP workers and describes the `kb-*` stream consumers as
  continuously-running and the batch producers as run-to-completion
  (`docs/designs/implemented/fleet_ladder_architecture.md:27-33`); the compose's cell-pool
  comment carries the same scoping (`infrastructure/docker-compose.ladder.yml:139-142`).
>>>>>>> 9d2c3c57d

### F5 — The mount-contract guard failure (real enforcement gap)
- **Evidence**: `tests/test_fleet_guards.py:85-118` fails on the compose repo-alias + `.git`
  overlay targets (`infrastructure/docker-compose.ladder.yml:59-64`); the failure is real and
  independently reproduced. Note: `scripts/fleet/spawn_wrapper.py`'s runtime allowlist
  ALREADY carries these mounts — the guard's test copy is stale, not the wrapper
  (admission_leases p5 confirmed this live).
- **Fix**: mirror the spawn-wrapper runtime allowlist into the guard (or make the guard
  consume the wrapper's allowlist as the single source), then the guard passes and the
  authority's "open enforcement gap" line can flip to closed.
- **Severity**: high (the one FAIL finding that is a code/test defect, not doc prose).
- **Owner**: the running `fleet_job_submission` p4_isolation_guards (sonnet, in flight —
  the spec's p4 demands exactly this contract) + admission_leases p5 (already touching it).
<<<<<<< HEAD
=======
- **Closure evidence**: [M] the guard's `ALLOWED_MOUNT_TARGETS` now mirrors the wrapper's
  runtime `CONTRACT_TARGETS` (repo-alias + `.git` overlays —
  `tests/test_fleet_guards.py:86-102` vs `scripts/fleet/spawn_wrapper.py:79-97`); [M] both
  directions are asserted — `test_mount_contract_holds_no_unexpected_target` passes on the
  declared compose targets and `test_mount_guard_rejects_a_foreign_target` proves an invented
  mount still fails (`tests/test_fleet_guards.py:136-161`); the guard is not weakened. [M]
  The authority and the implemented design flip the enforcement-gap line to the passing
  current state (`ARCHITECTURE.md:248-253`, `docs/designs/implemented/fleet_ladder_architecture.md:58-62`).
>>>>>>> 9d2c3c57d

## Coordination note (not a FAIL finding)
The branch's compose-comment edits (`infrastructure/docker-compose.ladder.yml:1-8,257-260`
— "Direct Internet egress remains possible until cells are configured to use that proxy")
are honest documentation of F1. When `fleet_job_submission` p5_egress_proxy_enforcement
lands, those comments become stale again — the remediation phase must re-touch them (and the
ARCHITECTURE.md §6 isolation line) at the same time.

<<<<<<< HEAD
## Acceptance gate (re-verification before merge)
1. The five adversary checks (a)–(e) re-run clean on the remediated branch — in particular
   (a) every cited anchor resolves, (b) every new claim is tagged + anchored.
2. `tests/test_fleet_guards.py` passes (F5 closed) and the authority's "open enforcement
   gap" line is removed.
3. `python3 -m pytest tests/test_doc_lifecycle.py tests/test_dependency_direction.py
   tests/test_script_classification.py tests/test_spec_status.py tests/test_agent_config_render.py
   -q` — green.
4. `python3 scripts/_gen_instructions.py` re-run leaves `git diff --exit-code` clean
   (surfaces regenerated, not hand-edited).
5. The merge re-runs `sync_surfaces.py` + `spec_status.py` on the merged tree (the branch
   predates the newest specs; the derived index must be regenerated post-merge, per the
   beta-lab merge pattern).
=======
**Egress note — re-touched (closure).** [M] The compose comments now state direct egress as the
current operating reality, not as an open fix (`infrastructure/docker-compose.ladder.yml:3-6,260`)
and ARCHITECTURE.md §6 does the same, explicitly marking the proxy as the declared policy
point that is "not yet the enforced route — stated as current operating reality, not as an
open fix" (`ARCHITECTURE.md:294-298`). No cell scope configures `HTTP_PROXY`/`HTTPS_PROXY`
(verified by `grep` over the compose — only the comments and the `EGRESS_ALLOWLIST` env
reference the proxy).

## Acceptance gate (re-verification before merge)

**Result: PASS — all five steps re-verified on the remediated branch (2026-09-01, the
`docs_refresh_remediation` p4 phase).** Every gate re-run happened on the committed
remediation state (`cbb0b06a1` + `6b768a952`), not on the pre-fix tree.

1. **The five adversary checks (a)-(e) re-run clean — PASS.**
   - (a) every cited anchor resolves and says what the doc claims — [M] a scripted scan over
     the branch's touched-added lines resolved every `file:line` anchor; the only non-resolved
     patterns were brace-expansion (`src/agentic_dynamics/{core,...}/__init__.py:1`) and
     doc-relative references with an implied `docs/fleet/` prefix (slice-log anchors), all of
     which resolve by construction. The F1 re-points, F2 tags, F3 seam anchors, F4 scope, and
     F5 guard anchors were each spot-verified against source.
   - (b) no invented flags, paths, or models — [M] `python3 scripts/run_workflow.py --help`
     lists `--orchestrator`, `--cap-snapshot`, `--cap-shadow`, `--no-fact-emit`,
     `--change-analysis`, `--only-phase`, and the rest; the `agentic-dynamics` CLI surface
     matches the documented dispatcher. No invented interface appears in the remediated claims.
   - (c) doc-lifecycle vocabulary holds — [M] the doc-lifecycle guard passes (gate 3); the
     touched docs carry `status:` from the enforced vocabulary (`ARCHITECTURE.md` `accepted`,
     the fleet design `implemented` + `implemented_by`, the fleet docs `proposed` + the
     supersession banner, this record `accepted` frontmatter recording an implemented
     disposition).
   - (d) each theme has [M]/[C] evidence and no claim describes the old system as current —
     [C] layer (module count + spine tagged/anchored), context (cap_2b corrected to
     proposal-only-with-anchored-applied-path), docker (fleet design scoped), isolation
     (fleet docs superseded + the egress note as current reality).
   - (e) derived surfaces regenerated, not hand-edited — [M] gate 4's renderer re-run is
     diff-clean; the spec index/STATUS were regenerated by `scripts/spec_status.py` (gate 5).
2. **`tests/test_fleet_guards.py` passes (F5 closed) and the authority's "open enforcement
   gap" line is removed — PASS.** [M] 23 passed (including the new
   `test_mount_guard_rejects_a_foreign_target`); `git grep "open enforcement gap"`
   `ARCHITECTURE.md` + `docs/designs/implemented/fleet_ladder_architecture.md` returns nothing
   (the historical mention survives only in the adversary review's recorded finding, as it
   should).
3. **The five-suite pytest — PASS.** [M]
   `python3 -m pytest tests/test_doc_lifecycle.py tests/test_dependency_direction.py
   tests/test_script_classification.py tests/test_spec_status.py tests/test_agent_config_render.py
   -q` → **84 passed**.
4. **`python3 scripts/_gen_instructions.py` re-run leaves `git diff --exit-code` clean — PASS.**
   [M] 38 surfaces written, both schemas validated OK, `git diff --exit-code` exit 0.
5. **The spec index is regenerated and both specs read correctly — PASS.** [M]
   `python3 scripts/spec_status.py` regenerates `experiments/specs/index.json` + `STATUS.md`
   (166 specs; the branch's copy of `docs_refresh_remediation.yaml` is indexed). [C]
   `docs_architecture_refresh` reads `runnable` and `supersedes: opencode_docs_refresh`
   (the chain holds — `opencode_docs_refresh` is `completed`); `docs_refresh_remediation`
   reads `runnable` with an empty supersedes row. The merge re-runs `sync_surfaces.py` +
   `spec_status.py` on the merged tree per the beta-lab merge pattern.

## New findings recorded (not fixed — per the phase contract)

- **[C] `docs/reviews/docs_architecture_refresh_known_safe.md:16` describes the mount-guard
  mismatch as an accepted limitation** ("the guard fails on `/home/drseuss/ai-finops-framework`
  because compose declares the target while the allowlist omits it") — that state was the
  pre-remediation truth, and the F5 closure (this plan's finding 5) made the row stale: the
  guard now passes on the declared targets and still fails on a foreign one. The row is
  historical review evidence; updating it was not in the operator's five-finding scope, so it
  is recorded here rather than edited.
>>>>>>> 9d2c3c57d
