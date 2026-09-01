---
status: accepted
supersedes:
---

# docs_architecture_refresh — remediation plan (adversary FAIL findings)

**Status: implemented (operator-signed remediation plan) — frontmatter `accepted` per the
doc-lifecycle kind-tree contract (`docs/reviews/*` → `accepted`).** Source: the p4 adversarial review
(`docs/reviews/docs_architecture_refresh_adversary.md`, verdict FAIL — findings recorded,
fixes deferred per the spec's contract: "remediation remains an operator decision or a
follow-up phase"). This plan is the operator's decision: every FAIL finding below is
accepted, assigned, and gated on re-verification before the branch may merge. The five-point
acceptance gate has now re-run clean on the remediated branch and is recorded in
[§ Acceptance gate](#acceptance-gate-re-verification-before-merge) below.

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
- **Closure evidence**: [C] every audit anchor re-pointed
  (`docs/architecture/current/2026-09-01_docs_drift_audit.md:22,70,71,73,79` — the proposed
  location replaced by `docs/designs/implemented/fleet_ladder_architecture.md`); [M] both
  fleet docs carry the lifecycle-supersession banner for their operational claims
  (`docs/fleet/00_proposal.md:7-12`, `docs/fleet/01_infra_inventory.md:7-11`); [M] the deleted
  proposed path appears nowhere in the branch's `docs/` (`git grep` clean — see the gate's
  check (a) evidence).

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
- **Closure evidence**: [C] the module count is now `[C]`-tagged with the exact command and a
  pinned SHA (`ARCHITECTURE.md:46-49` — 107 modules at `806c0d344`, verified by re-running
  `git ls-files 'src/agentic_dynamics/**/*.py' | wc -l`); [M] the spine is `[M]`-tagged and
  anchored to the lint's tier model + the eight plane `__init__.py` import maps
  (`ARCHITECTURE.md:109-116`); [C] the CAP-consumption table now carries per-row `[C]` anchors
  to the consuming modules, the campaign specs, and the score artifacts
  (`ARCHITECTURE.md:161-194`).

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
- **Closure evidence**: [C] the corrected claim anchors the applied path to the campaign's own
  `apply_only_in_adaptive_arm` invariant + the score artifact (3 applied cells in
  `experiments/results/cap_2b/cap_2b_score_20260826T160018Z.json`) and explicitly separates it
  from the I7 `control_route` seam, which no committed spec sets
  (`ARCHITECTURE.md:180`, `workflows/repository/cap_2b.yaml:36-37,64-66`,
  `tests/test_context_plane_seam.py:271-284`). The opt-in decision remains the operator's.

### F4 — Fleet design overgeneralization
- **Evidence**: `docs/designs/implemented/fleet_ladder_architecture.md:27-30` claims all
  cell services process one queue job at a time, contradicted by the stream consumers,
  long-running daemons, and batch producers in `infrastructure/docker-compose.ladder.yml:167-257`.
- **Fix**: scope the claim to the story pool (the queue workers); describe the stream
  consumers/daemons as long-running units.
- **Severity**: medium (wrong architecture description in the new authority doc).
- **Owner**: remediation phase.
- **Closure evidence**: [M] the design now scopes "one queue job at a time" to the
  story/analysis/review BRPOP workers and describes the `kb-*` stream consumers as
  continuously-running and the batch producers as run-to-completion
  (`docs/designs/implemented/fleet_ladder_architecture.md:27-33`); the compose's cell-pool
  comment carries the same scoping (`infrastructure/docker-compose.ladder.yml:139-142`).

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
- **Closure evidence**: [M] the guard's `ALLOWED_MOUNT_TARGETS` now mirrors the wrapper's
  runtime `CONTRACT_TARGETS` (repo-alias + `.git` overlays —
  `tests/test_fleet_guards.py:100-133` vs `scripts/fleet/spawn_wrapper.py:103-121`); [M] both
  directions are asserted — `test_mount_contract_holds_no_unexpected_target` passes on the
  declared compose targets and `test_mount_guard_rejects_a_foreign_target` proves an invented
  mount still fails (`tests/test_fleet_guards.py:167-192`); the guard is not weakened. [M]
  The authority and the implemented design flip the enforcement-gap line to the passing
  current state (`ARCHITECTURE.md:248-253`, `docs/designs/implemented/fleet_ladder_architecture.md:58-62`).

## Coordination note (not a FAIL finding)
The branch's compose-comment edits (`infrastructure/docker-compose.ladder.yml:1-8,257-260`
— "Direct Internet egress remains possible until cells are configured to use that proxy")
are honest documentation of F1. When `fleet_job_submission` p5_egress_proxy_enforcement
lands, those comments become stale again — the remediation phase must re-touch them (and the
ARCHITECTURE.md §6 isolation line) at the same time.

**Egress note — re-touched (closure).** [M] The compose comments now state direct egress as the
current operating reality, not as an open fix (`infrastructure/docker-compose.ladder.yml:3-6,260`)
and ARCHITECTURE.md §6 does the same, explicitly marking the proxy as the declared policy
point that is "not yet the enforced route — stated as current operating reality, not as an
open fix" (`ARCHITECTURE.md:294-298`). No cell scope configures `HTTP_PROXY`/`HTTPS_PROXY`
(verified by `grep` over the compose — only the comments and the `EGRESS_ALLOWLIST` env
reference the proxy).

## Docs-drift inventory closure (the 9 findings — the run's goal context)

The `docs_refresh_remediation` run (this branch, p1 `4f788191c` + p2 `1bbe2919a` + p3
`6a651c8b8` + p4) was dispatched from the docs-drift proposal gate against the drift
inventory (`experiments/results/docs_drift/proposal.json`, 9 findings: 5 `anchor_integrity`
stale, 4 `cli_surface` missing). The p1 phase closed all nine; the p4 gate re-verified them.
Per-finding closure evidence:

| Finding | Closure evidence |
|---|---|
| `cli_surface/mental_model_full_cli/complete/--campaign-budget-usd` | [M] `--campaign-budget-usd` now enumerated in the mental-model FULL CLI marker block (`agent_config/mental-model.md:433-437`), re-rendered to both derived surfaces by the generator (`.opencode/instructions/mental-model.md:433-437`, `.claude/rules/mental-model.md:433-437`); `python3 scripts/run_workflow.py --help` lists it (scripts/run_workflow.py argparse). |
| `cli_surface/mental_model_full_cli/complete/--campaign-concurrency` | [M] same block + generator re-render; `--help` lists it. |
| `cli_surface/mental_model_full_cli/complete/--cell-image` | [M] same block + generator re-render; `--help` lists it. |
| `cli_surface/mental_model_full_cli/complete/--no-admission` | [M] same block + generator re-render; `--help` lists it. |
| `anchor_integrity/…/claude_tools_to_skills_scope.md:152/admin/server.py:1365` | [M] the port claim re-pointed to `apps/control_room/server.py:214`; the route listing to `apps/control_room/routes/{telemetry.py:375-378,flags.py:90,design_sessions.py:159,claude_agents.py:283}` (`docs/architecture/current/claude_tools_to_skills_scope.md:145-157`). |
| `anchor_integrity/…/claude_tools_to_skills_scope.md:311/admin/server.py:779-802` | [M] the `/api/status` SSE anchor re-pointed to `apps/control_room/routes/telemetry.py:137-160` (`:305-313`) with the generator loop at `telemetry.py:146-152`. |
| `anchor_integrity/…/claude_tools_to_skills_scope.md:318/admin/server.py:738-776` | [M] the `/api/matrix` jsonify anchor re-pointed to `apps/control_room/routes/telemetry.py:66-134` (`:318`). |
| `anchor_integrity/…/context_abstraction_addendum_design.md:399/verify.md:258-262` | [M] the fact-clearance anchor re-pointed to `docs/verification/context_abstraction_verify.md:253-263` (`:399`). |
| `anchor_integrity/…/routing_design.md:420/admin/server.py:860-877` | [M] the `compute_routing`/`recommend_route` consumer anchor re-pointed to `apps/control_room/routes/telemetry.py:205-219` (`:420`). |

[M] Every re-pointed target resolves (the cited files carry the cited lines); the deleted
`admin/server.py:NNN` / `verify.md:NNN` anchors appear nowhere in `docs/architecture/current/`
(`git grep` clean); `docs scan --fail-on-drift` for `anchor_integrity` (571/571 current) +
`cli_surface` (160/160 current) is clean on this branch. The four cli_surface fixes were made
in the SOURCE doc (`agent_config/mental-model.md`) and propagated by the generator — derived
surfaces were never hand-edited (gate 4's diff-clean re-run is the proof).

## Acceptance gate (re-verification before merge)

**Result: PASS — all five steps re-verified on the remediated branch (2026-09-01, the
`docs_refresh_remediation` p4 phase).** Every gate re-run happened on the committed
remediation state (this branch's p1 `4f788191c` + p2 `1bbe2919a` + p3 `6a651c8b8`,
building on the earlier closure commits `cbb0b06a1` + `6b768a952`), not on the pre-fix
tree — and additionally covered the docs-drift inventory's 9 findings
([§ Docs-drift inventory closure](#docs-drift-inventory-closure-the-9-findings)).

1. **The five adversary checks (a)-(e) re-run clean — PASS.**
   - (a) every cited anchor resolves and says what the doc claims — [M] a scripted scan over
     the branch's touched-added lines resolved every `file:line` anchor; the only non-resolved
     patterns were brace-expansion (`src/agentic_dynamics/{core,...}/__init__.py:1`) and
     doc-relative references with an implied `docs/fleet/` prefix (slice-log anchors), all of
     which resolve by construction. The F1 re-points, F2 tags, F3 seam anchors, F4 scope, and
     F5 guard anchors were each spot-verified against source, as were the nine docs-drift
     re-points (the `admin/server.py:NNN` / `verify.md:NNN` anchors now cite
     `apps/control_room/{server.py,routes/*}` and `docs/verification/context_abstraction_verify.md`
     — § Docs-drift inventory closure). `docs scan --fail-on-drift` is clean on this branch
     (anchor_integrity 571/571, cli_surface 160/160 current, drift 0).
   - (b) no invented flags, paths, or models — [M] `python3 scripts/run_workflow.py --help`
     lists `--orchestrator`, `--cap-snapshot`, `--cap-shadow`, `--no-fact-emit`,
     `--change-analysis`, `--only-phase`, `--cell-image`, `--no-admission`,
     `--campaign-budget-usd`, `--campaign-concurrency`, and the rest; the `agentic-dynamics`
     CLI surface matches the documented dispatcher. No invented interface appears in the
     remediated claims.
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
   gap" line is removed — PASS.** [M] 24 passed (including the new
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
   (177 specs; the branch's copy of `docs_refresh_remediation.yaml` is indexed). [C]
   `docs_architecture_refresh` reads `completed` (its run ledger
   `experiments/results/workflows/docs_architecture_refresh/20260831T235230Z.json`) with
   `supersedes: opencode_docs_refresh` (the chain holds — `opencode_docs_refresh` is
   `completed`); `docs_refresh_remediation` reads `completed` (its run ledger
   `experiments/results/workflows/docs_refresh_remediation/20260901T010140Z.json`) with an
   empty supersedes row. The prior record's `runnable` reads reflected the pre-ledger tree;
   the current reads post-date both run ledgers and the chain is consistent. The merge re-runs
   `sync_surfaces.py` + `spec_status.py` on the merged tree per the beta-lab merge pattern.

## New findings recorded (not fixed — per the phase contract)

- **[C] `docs/reviews/docs_architecture_refresh_known_safe.md:16` describes the mount-guard
  mismatch as an accepted limitation** ("the guard fails on `/home/drseuss/ai-finops-framework`
  because compose declares the target while the allowlist omits it") — that state was the
  pre-remediation truth, and the F5 closure (this plan's finding 5) made the row stale: the
  guard now passes on the declared targets and still fails on a foreign one. The row is
  historical review evidence; updating it was not in the operator's five-finding scope, so it
  is recorded here rather than edited.

- **[C] The docs-drift watchdog's machine artifacts still carry the raised flag for the
  pre-fix scan** — `experiments/results/docs_drift/{latest.json,proposal.json,flag_state.json}`
  and `history.jsonl` record drift 9 at git_sha `ec4b7bda` with `state: raised`, and
  `proposal.json` is `state: warranted` with `approval: {}`. Those are derived
  rail artifacts rewritten by the next `docs_drift_watchdog.py` pass (which reads the current
  tree — drift 0 — and clears the flag as an EDGE transition); the run's scan evidence is
  committed as `experiments/results/docs_drift/scan_now.json` (p2) + `gate_scan.json` (p4).
  Clearing the flag / releasing the proposal is the proposal gate's terminal transition, owned
  by the workflow's completion — out of the p4 gate-record scope, so recorded here rather than
  edited.
