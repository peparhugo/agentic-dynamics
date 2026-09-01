---
status: accepted
---

# Docs architecture refresh - adversarial review

**Verdict: FAIL.** [C] The independent pass finds unresolved historical anchors, unsupported or
untagged current claims, and current-state drift in all four required themes. This review records
findings only; remediation remains an operator decision or a follow-up phase
(`workflows/repository/docs_architecture_refresh.yaml:175-189`).

| Check | Result | Evidence |
|---|---|---|
| (a) Every claimed `file:line` anchor resolves and says what the document claims | **FAIL** | [M] The p1 audit identifies its historical checkout (`docs/architecture/current/2026-09-01_docs_drift_audit.md:11`) but still cited the then-proposed design (moved post-audit to `docs/designs/implemented/fleet_ladder_architecture.md`) at `:22,70-73,79`; at review time those current-tree anchors could not resolve. [C] The refreshed module-count, dependency-spine, and CAP-consumption claims carry neither an inline provenance tag nor a repository-relative source anchor (`ARCHITECTURE.md:46-49,110,155-182`), so they cannot satisfy the required claim-to-evidence contract. [M] The moved fleet design's claim that all cell services process one queue job at a time is contradicted by the declared stream consumers, long-running daemons, and batch producers (`docs/designs/implemented/fleet_ladder_architecture.md:27-30`, `infrastructure/docker-compose.ladder.yml:167-257`). |
| (b) No invented flags, paths, or models | **PASS** | [M] `python3 scripts/run_workflow.py --help` lists `--orchestrator`, `--cap-snapshot`, `--cap-shadow`, `--no-fact-emit`, `--change-analysis`, and `--only-phase`; the parser and associated wiring are in `scripts/run_workflow.py:225-291`. [M] The checkout-local CLI help from `python3 -m agentic_dynamics.cli --help` matches the dispatcher table and documented surface (`src/agentic_dynamics/cli.py:21-105,121-156`); the `agentic-dynamics` shell entry point is not installed in this environment. [M] The workflow model is `openai/gpt-5.6-terra` (`workflows/repository/docs_architecture_refresh.yaml:190-192`). [C] The stale historical path in check (a) is an unresolved reference, not an invented current interface. |
| (c) Doc-lifecycle vocabulary holds for the touched documentation | **PASS** | [M] `ARCHITECTURE.md`, `README.md`, the p1 audit, and this review use `status: accepted`; the moved fleet design uses `status: implemented` with `implemented_by` (`ARCHITECTURE.md:1-4`, `README.md:1-3`, `docs/architecture/current/2026-09-01_docs_drift_audit.md:1-3`, `docs/designs/implemented/fleet_ladder_architecture.md:1-5`). [M] `python3 -m pytest tests/test_doc_lifecycle.py tests/test_dependency_direction.py tests/test_script_classification.py tests/test_spec_status.py tests/test_agent_config_render.py tests/test_fleet_guards.py -q` produced 105 passes; the only failure was the separate mount-contract guard (`tests/test_doc_lifecycle.py:64-130`, `tests/test_fleet_guards.py:111-118`). |
| (d) Each theme has [M]/[C] evidence and no claim describes the old system as current | **FAIL** | [C] **Layer: FAIL.** The revised plane count and dependency spine are untagged and unanchored (`ARCHITECTURE.md:46-49,110`). [M] **Context: FAIL.** The authority says cap_2b applies accepted proposals (`ARCHITECTURE.md:172`), while the application seam requires `workflow.params.control_route: true` (`src/agentic_dynamics/control/rules.py:12-19`) and the committed corpus has no opt-in (`tests/test_context_plane_seam.py:271-284`). [M] **Docker: FAIL.** The implemented fleet design overgeneralizes story-worker behavior to all cell services (`docs/designs/implemented/fleet_ladder_architecture.md:27-30`, `infrastructure/docker-compose.ladder.yml:167-257`). [M] **Isolation: FAIL.** Current fleet documents still linked to the then-proposed design (`docs/fleet/00_proposal.md:11`, `docs/fleet/01_infra_inventory.md:9`) rather than the implemented design; their former operational claims were discoverable without a lifecycle supersession. |
| (e) Derived surfaces were regenerated, not hand-edited | **PASS** | [M] Re-running `python3 scripts/_gen_instructions.py` wrote 38 surfaces, validated both schemas, and left `git diff --exit-code` clean. [M] The renderer-drift and orphan guards passed in the test run; they compare committed outputs against renderer output and reject files outside the renderer mapping (`tests/test_agent_config_render.py:150-193`). |

## Guard Limitation

[C] The mount-contract failure was real and independently reproduced at review time: compose
declared repository alias and `.git` overlay targets outside the guard allowlist
(`infrastructure/docker-compose.ladder.yml:59-64`, `tests/test_fleet_guards.py:85-118`), and the
refreshed authority then recorded it as an open enforcement gap, so it was not counted as evidence
that the isolation contract is proven. [P] F5 of the operator-signed remediation (below) aligns the
guard's allowlist with the wrapper's runtime `CONTRACT_TARGETS`, which already carried those
targets, so the guard passes without weakening the mount contract.

## Disposition

[P] The operator-signed remediation (2026-09-01) closed all five findings:

| Finding | Closure |
|---|---|
| **F1 — stale anchors** | Every audit/fleet-doc reference re-pointed to `docs/designs/implemented/fleet_ladder_architecture.md`; `docs/fleet/00_proposal.md` + `docs/fleet/01_infra_inventory.md` carry lifecycle-supersession notes for their operational claims; the deleted proposed path appears nowhere in `docs/`. |
| **F2 — unanchored claims** | `ARCHITECTURE.md:46-49,110,155-182` re-tagged with [C]/[M] provenance and resolving anchors (pinned-SHA module count, lint + plane-`__init__` spine, per-claim CAP-consumption anchors). |
| **F3 — cap_2b proposal-only** | The cap_2b apply claim anchored to the campaign's own `apply_only_in_adaptive_arm` invariant + the score artifact, and distinguished from the I7 `control_route` seam (which no committed spec sets). |
| **F4 — fleet overgeneralization** | The implemented design's "one queue job at a time" claim scoped to the story pool; stream consumers/daemons described as long-running units. |
| **F5 — mount-guard alignment** | `tests/test_fleet_guards.py`'s allowlist aligned with the wrapper's runtime `CONTRACT_TARGETS` (repo-alias + `.git` overlays); the mount guard passes and is not weakened. |

[P] The egress comments (`infrastructure/docker-compose.ladder.yml` + `ARCHITECTURE.md` §6) re-state
direct egress as the current reality rather than as an open fix.
