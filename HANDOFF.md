---
status: accepted
---

# HANDOFF — session 2026-09-01: the measurement wave + the degradation findings

**Status: the session's work is merged and pushed (`708154029`). This document is the
operator's pick-up surface — the next session starts here. TWO agents' findings are carried
forward: the operator-session's registry/DLQ findings + an independent agent's degradation
review of the recent workflow era. Both are named below with their pending decisions.**

## 1. What the session accomplished (all merged + pushed to main)

| commit | what landed |
|---|---|
| `d564f89c4` → `708154029` | **six workflow merges**: the retrieval gate closure (augmentation verified end-to-end: retrieve `full`/35 candidates, constructor plan `sha256:988fa80d` reproduced twice), `retrieval_fusion_quality` (the **H2 two-view verdict**: the dense+lexical stores index genuinely disjoint units, `content_pairs=0` across 4 census runs — fused=0 is a deliberate two-view outcome, not a fusion defect), `control_room_live_board` (the LIVE NOW section), `test_suite_speed` (workflow_runner 187→38.8s; the 132s root-commit test was a thread-join wait; full suite 15min→7min; the `fast` marker + budget gate), `automatic_docs_sync` (the **docs-drift rail**: scan_docs_drift.py — 1,181 anchored claims, zero model calls; its FIRST baseline found 9 real findings; the proposal gate + docs-health panel; **the full loop ran end-to-end: detect 9 → propose → approve → remediate ($0.17) → DRIFT SCORE 0 → flag cleared**), plus `beta_lab_execution`, `docs_architecture_refresh` + `docs_refresh_remediation`, `fleet_job_submission`, `control_room_usage_wiring`, `context_abstraction_closure`, `delta_entropy_response_campaign` (spec only) |
| `143d31b1f` | **runner truth**: `AugmentationOutcome.error` records the swallowed constructor exception; `PhaseResult.timed_out` marks wall-burning phases (a clean ok can no longer mask lost evidence — the retrieval p4's 1800.16s-at-1800s, ok=True shape) |
| `9a4d83623` | **retrieval perf**: the cosine-collapse embed fan-out capped (top-24, 8-thread pool) — 31.5s → 6.2s per retrieve |
| `f8d4e9880` | the **β reframe**: β is a contention exponent, not a coordination tax (this architecture has zero agent coordination by design); robust readings β_cost 0.11–0.14 / β_tokens 0.26–0.43 vs the tail-inflated OLS 0.154/0.800; the lease_registry docstring + the lab book + the sensitivity note carry it |
| `6980258cb` + `5eb392a10` + `4be2780f0` | the **portal truth fixes**: a running cell whose phase is definitively past the 10-min window re-presents as ENDED (window, not the process, decides); the tail-stamp bug (head-only read + event-as-part) fixed; the flat running count follows the override |
| `cc8c2c490` | the **tailnet trust gate**: the portal binds Tailscale-only, so the tailnet CGNAT range (100.64.0.0/10) is accepted as the operator alongside loopback (the remote approve path works) |
| `37a69fceb` + `dbc7bca69` + the compose fix | the **fleet submit path** made real: the workflow-runner compose command fixed to `spawn_wrapper.py consume`, the docs_refresh_remediation phases authorized, the consume loop survives transient Redis socket timeouts — but the **in-process fallback remains the proven default** (the fleet path's first live use hit the compose/auth/crash cascade) |
| `708154029` | the **registry backfill**: re-emitted the missing kb-record events (+250 fact rows recovered); the remaining gap is pre-existing (see §3) |

## 2. The machine's live state

- Main green + pushed at `708154029`. Spec index: 175 (11 experiments + 164 workflows).
- No workflows running; the fleet consume container is down (its fixes are committed); the portal (systemd, Tailscale `100.83.229.3:8001`) serves the LIVE NOW + ENDED + docs-health surfaces.
- The docs-drift rail is armed: the scanner's watchdog cadence + the proposal gate; the flag is clear (DRIFT SCORE 0).
- The Anthropic 5h window resets 02:10 CEST; OpenAI primary at 4% of a 7-day window (the 09-01 usage readings).

## 3. FINDINGS (carry into the fresh session)

### 3a. The operator-session's registry/DLQ findings

- **Zero knowledge entries are lost** — 18,436 kb artifacts on main + 44 unique on the worktrees; all intact.
- **`kb-registry-v1` has been dead-lettering whole source types since August**: the DLQ (`kb:v1:dead_letter`) holds **4,173 entries**; `code` (1,073 records), `finding` (804), `policy` (34), `actuation` (11) never receive registry rows because the consumer's extractor fails for them → the registry index covers 16,501 of 18,436 artifacts; the remaining **1,935 are the DLQ'd types (pre-existing, not caused by the 09-01 session)**.
- The 09-01 stash-drop cost a small slice of the *fact* rows in the derived index (uncommitted appends stashed+dropped during merges — the operator's merge hygiene mistake); recovered by the backfill. The kb record artifacts were never at risk (untracked files are never stashed).
- **Open: why does the extractor fail for code/finding/policy/actuation?** + a DLQ re-process pass (scripts/fleet/dlq_triage.py exists). Candidate: the `measured-finding/v1` + `code/v1` extractors vs the registry row schema.

### 3b. The independent agent's degradation review (verbatim markers)

1. **The independent test gate is gone from the recent specs.** The gated-era workflows had a `kind: test` phase where the harness independently ran `run_suite` and recorded `test_executed_success` (routing_kb_more_itertools 732/732, rag_knowledge_base_build 699/699, opencode_docs_refresh 530/530). Every recent workflow dropped it: all phases in `docs_refresh_remediation`, `test_suite_speed`, `control_room_live_board`, `retrieval_fusion_quality`, `automatic_docs_sync`, `fleet_job_submission`, `retrieval_activation` are `kind: agent`, and every phase ledger shows `test_executed_success: None, tests 0/0`. The "gate" phases (`p4_gate`, `p4_acceptance_gate`, `p3_gate_recensus`) are *agent* phases that self-report "84 passed" in the commit message — never independently measured by the harness. Specs with `kind: test` fell from 4–5/11–13 per day (08-26→08-29) to 1/16 on 09-01.
2. **`files_modified` is now a broken measurement.** `src/agentic_dynamics/adapters/opencode.py:550` computes `files_modified` as `files_after & files_before` — the set of files that existed *before* the run, not files whose content changed. In the big worktrees the recent workflows run in, that's the entire repo: every recent phase ledger shows ~31,500 "modified" files (vs 39 in the small fork-era routing run). The per-phase change signal is meaningless now.
3. **Phase commit hygiene degraded.** `docs_refresh_remediation` run2's `p2_context_claim` committed twice; the run's recorded phase commit (`1bbe2919a`) only adds a scan artifact, while the real F3 fix is in the sibling commit `f5f66e07d`. `retrieval_fusion_quality`'s `p1_overlap_instrument` committed 4×; the recorded phase commit `c2ad8944d` is only README/spec-index/session regen — the substantive instrument is `9929caa1b`.

**Cost signal (the reviewer's):** the gated era spent on judgment: opus $47.52 (automatic_docs_sync), sonnet $10.39 (retrieval_activation). The last several are all flash at $0.14–$0.36 total — consistent with the specs no longer demanding independent verification.

## 4. Open items (owned or pending)

1. **The DLQ/extractor fix** (3a): why code/finding/policy/actuation fail extraction + the re-process pass. Candidate: a small flash spec (`registry_dlq_repair`).
2. **The reviewer's (a)/(b)/(c) decision**: (a) fix the `_diff_workdir` files_modified bug (opencode.py:550 — changed-set, not pre-existing-set); (b) restore `kind: test` gate phases to the recent specs (the 09-01 specs are all agent-phased); (c) both — **recommend (c)**.
3. **The runner's test-phase wall**: `kind: test` phases run the WHOLE tree via `run_suite` (600s wall — the augment-proof died on it). `test_suite_speed`'s p2 claimed the scoped run_suite — **VERIFY whether the scoped target landed in the merged code** (the merge message claims it; the merged suite runs need confirmation).
4. **The fleet submit path**: fixed but never end-to-end green (compose consume command + auth entries + consume-loop retry are committed; the first live submit was refused then the loop crashed — re-verify with a trivial submit).
5. **The auth-table drift class**: `PHASE_SCOPE_AUTHORIZATION` misses entries for recently-authored specs (p5 + the remediation phases both tripped it) — the docs-drift scanner's cli_surface axis should also check the auth table.
6. **The proof's 9 findings** were the anchor_integrity + cli_surface axes; the scanner's other axes (module inventory, status vocabulary, manifests) are unexercised — worth one full-scan exercise.

## 5. Next moves (the fresh session's pick list)

1. Decide (a)/(b)/(c) — the reviewer recommends both; the test gate restoration is the higher-order fix (it restores the harness's independent verification, which the 09-01 specs stopped demanding).
2. Fix `opencode.py:550` files_modified (changed-set semantics) — small, high-signal.
3. The `registry_dlq_repair` spec: fix the extractor + drain the 4,173 DLQ entries + re-verify coverage 18,436/18,436.
4. Verify the scoped run_suite (open item 3) + land the runner's test-phase targeting.
5. Re-verify the fleet submit path with a trivial submit (open item 4).
6. Extend the docs-drift scanner with the auth-table axis (open item 5).
