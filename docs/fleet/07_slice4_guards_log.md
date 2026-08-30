---
status: accepted
---

# Fleet-ladder slice 4 — the audit guards (the full suite green)

**Status: PASS · Date: 2026-08-30 · Role: slice 4 (`fleet_ladder_implementation` p5 — the
execution phase).** Builds the seven read-only guard tests (proposal §7 slice 4, §8), runs the
full deterministic suite green, and reconciles the data chain the guards surfaced. Every finding
is a test result or a file assertion.

## 0. Verdict

**PASS.** The seven guards are written in `tests/test_fleet_guards.py` (22 tests), the full
deterministic suite is green — `python3 -m pytest tests/ -m "not external" -q` →
**2201 passed, 116 deselected, 0 failed** — and the two data-chain drifts the guards exposed
were fixed in the implementation (not the guard): the README "By the Numbers" count and the
stale parquet/lab/data.js chain.

## 1. The seven guards (proposal §8)

| # | guard | asserts | tests |
|---|---|---|---|
| 1 | **compose-contract** (D-13/D-3) | every mount target ∈ the four + the D-2 auth set + the `fleet-logs` NAMED volume (no unexpected host path); the socket appears in **exactly one tier** (the orchestrator) and is `ro`; the supervisor holds no socket and no worktree mount; `fleet-logs` is declared a named volume | `test_mount_contract_holds_no_unexpected_target`, `test_socket_appears_in_exactly_one_tier`, `test_supervisor_has_no_socket_and_no_worktree_mount`, `test_fleet_logs_is_a_named_volume_not_a_host_path` |
| 2 | **fleet-health** (D-14) | the board surfaces worker heartbeats (`worker:<type>:<id>`) + per-queue DLQ counts (the `heartbeat.read_all` + `dlq.dead_counts` the manager reads) | `test_board_surfaces_heartbeats_and_dlq_counts` |
| 3 | **neo4j-index** (D-12/§6) | the `knowledge_text_ft` fulltext index is defined over `Knowledge.text`; the kb-neo4j handler writes `text` + calls `create_knowledge_schema` + skips `fact` (address, not relevance) | `test_fulltext_index_is_defined_over_knowledge_text`, `test_kb_neo4j_handler_writes_text_and_skips_facts` (+ a live `@external` pending↔index check) |
| 4 | **single-write-back** (D-11/G6) | exactly ONE kb consumer (`kb-registry`) carries `FINOPS_KB_WRITE=1`; the orchestrator + supervisor never do (D-15); `FINOPS_ACTUATION_ARMED` never set (G2) | `test_exactly_one_kb_consumer_carries_the_write_flag`, `test_orchestrator_and_supervisor_never_carry_the_write_flag`, `test_no_service_arms_actuation` |
| 5 | **binary-probe** (D-18) | `resolve_chain` passes a live executable and **fails loudly** on a missing launcher / non-executable target; `probe_all` resolves the two CLIs | `test_probe_valid_binary_passes`, `test_probe_missing_launcher_fails_loudly`, `test_probe_non_executable_target_fails_loudly`, `test_probe_all_resolves_the_two_clis` |
| 6 | **scope-vocabulary** (D-16) | every phase's `scope:` across the spec corpus ∈ the five-scope vocabulary; the authorization table is well-formed; the implementation workflow's phases each resolve to an authorized scope | `test_every_phase_scope_is_in_the_vocabulary`, `test_authorization_table_is_well_formed`, `test_implementation_workflow_phases_are_authorized` |
| 7 | **network-policy** (D-17) | every tier attaches to **exactly `fleet-net`** (no `host`/`bridge` network_mode); no ladder service publishes 6379 (finops-redis) or 4096 (opencode server); the portal binds loopback only (`127.0.0.1`); the egress proxy is on fleet-net | `test_every_tier_attaches_to_exactly_fleet_net`, `test_no_ladder_service_publishes_the_sandbox_or_server_ports`, `test_portal_binds_loopback_only`, `test_egress_proxy_is_the_single_policy_point_on_fleet_net` |

## 2. The suite result

`python3 -m pytest tests/ -m "not external" -q` → **2201 passed, 116 deselected (external),
0 failed** (291 s). The 116 deselected are the `external`-marked live-service tests (opencode /
Ollama / ChromaDB / Neo4j), exercised by the operator's smoke test — the slice-4 guard set is
all in the deterministic run.

## 3. The two drifts the guards exposed (fixed in the implementation)

Running the guards against the CURRENT state surfaced two REAL violations the slices left —
both fixed in the data/README, not the guard (the proposal's rule):

1. **The parquet / data.js / lab-artifact chain was stale.** The kb-registry consumer (live
   since slice 3) grew `registry_index.jsonl`, so `sessions.parquet`/`stories.parquet`, the 8
   canonical lab artifacts, `apps/website/data.js`, and `data_manifest.json` no longer matched.
   Fixed by re-running the canonical reproduction (`scripts/reproduce.sh`: inventory → sync →
   analyze → labs → build_data → manifest), which re-derives every number from the current
   corpus — 2201 green.
2. **The README "By the Numbers" DB-session total had drifted** (5,593 → 6,333 raw DB sessions,
   from the regenerated `public_statistics`). Updated both the table cell and the explanatory
   note.

## 4. Rollback

Read-only tests — nothing to roll back (proposal §7 slice 4).

## LOG

**PASS.** Seven read-only guard tests (`tests/test_fleet_guards.py`) cover the compose-contract
(mount contract + socket-in-one-tier), fleet-health (heartbeats + DLQ on the board), the neo4j
index (fulltext defined + handler writes text), the single-write-back (D-11), the binary probe
(D-18), the scope vocabulary (D-16), and the network policy (D-17). The full deterministic suite
is green (2201 passed, 0 failed); the two drifts the guards exposed (the stale data chain + the
README count) were fixed in the implementation, not the guard. Committed.
