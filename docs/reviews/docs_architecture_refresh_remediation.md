---
status: proposed
supersedes:
---

# docs_architecture_refresh — remediation plan (adversary FAIL findings)

**Status: proposed (operator-signed remediation plan).** Source: the p4 adversarial review
(`docs/reviews/docs_architecture_refresh_adversary.md`, verdict FAIL — findings recorded,
fixes deferred per the spec's contract: "remediation remains an operator decision or a
follow-up phase"). This plan is the operator's decision: every FAIL finding below is
accepted, assigned, and gated on re-verification before the branch may merge.

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

### F4 — Fleet design overgeneralization
- **Evidence**: `docs/designs/implemented/fleet_ladder_architecture.md:27-30` claims all
  cell services process one queue job at a time, contradicted by the stream consumers,
  long-running daemons, and batch producers in `infrastructure/docker-compose.ladder.yml:167-257`.
- **Fix**: scope the claim to the story pool (the queue workers); describe the stream
  consumers/daemons as long-running units.
- **Severity**: medium (wrong architecture description in the new authority doc).
- **Owner**: remediation phase.

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

## Coordination note (not a FAIL finding)
The branch's compose-comment edits (`infrastructure/docker-compose.ladder.yml:1-8,257-260`
— "Direct Internet egress remains possible until cells are configured to use that proxy")
are honest documentation of F1. When `fleet_job_submission` p5_egress_proxy_enforcement
lands, those comments become stale again — the remediation phase must re-touch them (and the
ARCHITECTURE.md §6 isolation line) at the same time.

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
