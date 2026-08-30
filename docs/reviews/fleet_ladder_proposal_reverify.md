---
status: accepted
---

# Fleet-ladder proposal — re-verification (round 2, the operator's design review)

**Status: accepted · Date: 2026-08-29T19:05Z · Source: p1_reverify (round 2) of the
`fleet_ladder_revision` spec (spec_sha256 `0d30d4bc…`, escalated to deepseek-v4-pro).** Target:
the **REVISED** `docs/fleet/00_proposal.md` (p0_revise round 2, which added the three
operator-refinements D-16/D-17/D-18). Method: re-run the p5 attack surface (F-A1…F-A7), the
round-1 revision surface (D-9…D-15), AND the new round-2 surface (D-16/D-17/D-18), in the
prescribed order — access-matrix completeness, guard preservation, the constraints, the neo4j
bridge, migration feasibility, then the new decisions. **A failed attack is NOT a finding; a
real hole is.**

## The finding-by-finding closure table

| # | p5 finding | re-verify (round 2) | resolution in the doc | closed by the mapping itself? |
|---|---|---|---|---|
| **F-A1** | R10 unmapped + the 37-touch miscount | **CLOSED** | R10 (`bundle_artifacts.py:53,116`) on the **supervisor** tier (§1b reads); risk R10 → D-10; completeness **14 reads (R1-R10, F-3…F-6) → 13 + 4 + 14 + 6 = 37** (§1b) | yes — §0 + §1a + §1b |
| **F-A2** | G6-vs-D11 dead (flag auto-clear never fires) | **CLOSED** | **guard wins**: kb-registry consumer granted `FINOPS_KB_WRITE=1` (D-11) → env gate (`kb_worker.py:198`) AND `authorized=True` (`:212`) both pass; slice-4 asserts exactly one consumer carries the env | yes — §0 (D-11) + §2 + §6 + §8 |
| **F-A3** | supervisor mount-contract breach | **CLOSED** | **D-13**: configs → `repo ro` (compose files), logs → the `fleet-logs` named volume (not a host path); supervisor mounts a subset of the four + that volume | yes — §0 (D-13) + §1a + §1b + §2 |
| **F-A4** | socket/watcher unspecified | **CLOSED** | **D-14**: static pools + `restart: on-failure`; read-only watcher; resize/drain over `fleet:commands` (db1, 6380) validated by the spawn-wrapper (compose allowlist + mount contract) before the socket call | yes — §0 (D-14) + §2 + §7 |
| **F-A5** | host-footprint D-9 | **CLOSED** | **D-9**: opencode server (4096) + 62 GB db reclassified **operator-side** (outside the ladder); host footprint of ours = the bootstrap unit only | yes — §0 (D-9) + §1a + §2 + §7 |
| **F-A6** | double-review window | **CLOSED** | **D-10**: review migration is a **cut-over** (stop host `trigger_reviews` + drain in-flight `review_all` FIRST); slice-1 rollback split additive/cut-over | yes — §0 (D-10) + §7 |
| **F-A7** | orchestrator env ambiguity | **CLOSED** | **D-15**: orchestrator never carries `FINOPS_KB_WRITE=1`; F-1/F-2/P11 authorize in code (`_authorized_kb_write()` / `authorized=`) | yes — §0 (D-15) + §2 + §8 |

## Per-attack detail

### (1) Access-matrix completeness — PASS (F-A1 re-attacked)
The renumbering (image → §4, neo4j → §6, slices → §7, guards → §8, REVISION LOG → §9) did not
disturb the placements. R10 sits in the supervisor's read list (§1b) next to R7/R8/R9/F-6; the
arithmetic is honest (13 + 4 + 14 + 6 = 37). Risk R10 → D-10 (§0 risk dispositions). **No
unmapped touch.**

### (2) Guard preservation — PASS (F-A2, F-A7 re-attacked; G1-G6 re-traced)
- **G1** (`knowledge_stream.py:184-186`): code untouched. Env holders are precise — P1-P10 cell
  writers + the kb-registry consumer (D-11); the orchestrator does not set it (D-15). **The
  scope model does not widen this**: in §5's vocabulary, only the `implementation` scope may
  carry `FINOPS_KB_WRITE=1` ("only if the phase emits, P1-P11"), and the spawn-wrapper's step-5
  check ("env = the scope's env") makes an undeclared write flag a spawn-time failure. The other
  four scopes are "no write flags". G1's placement is *tightened*, not weakened.
- **G2 actuation-armed** (`:188-191`): never set — no scope declares `FINOPS_ACTUATION_ARMED`;
  zero actuation producers. Preserved.
- **G3 lineage** (`:194-198`): code-side, untouched. Preserved.
- **G4 registry append**: the kb-registry consumer stays the sole appender; producers write only
  via the stream. Preserved.
- **G5 scope (two-channel)** (`self-<worktree>` / `scope_excluded`): per-cell env, unchanged.
  (Named disambiguation: G5's "scope" is the *KB* repository scope; D-16's "scope" is the
  *step* capability scope. The two coexist without conflict — G5 governs retrieval/emit, D-16
  governs the container config. Neither re-defines the other.)
- **G6 consumer read-only**: kb-registry consumer is the ONE kb-worker container with
  `FINOPS_KB_WRITE=1` (D-11), so the flag auto-clear's env gate passes; the slice-4 guard test
  asserts exactly one consumer carries it. The D-11/F-A2 tension stays resolved in the guard's
  favor.

### (3) The constraints — PASS (re-attacked)
- **Host bootstrap only:** held — D-9 reclassifies the opencode server + db operator-side.
- **Master control = the operator chat, no self-activation:** held — the supervisor is
  KB-read-only, the sign-off gate is explicit, nothing self-activates.
- **Socket = the ONE escalation (orchestrator tier only):** held — D-16's sibling *phases* get
  **no socket** (they are cell containers, "no socket" per §1a); only the orchestrator's
  spawn-wrapper makes the socket call. The scope model adds no second socket.
- **Mount contract, nothing beyond the four (incl. the supervisor):** held — D-13 absorbs the
  supervisor's two out-of-contract mounts; and **every scope in §5 is a subset of the four
  categories + the D-2 auth set** (the doc-writing scopes write into their *worktree*, never a
  fifth host path). No tier or scope mounts a host path beyond the four + D-2.

### (4) The neo4j bridge — NOT FALSIFIED (unchanged)
The kb-neo4j-v1 spec is intact and buildable from the proposal alone: tier (cell), image
(`fleet/base` + `[neo4j]` extra), access (stream read → `create_knowledge_schema` + idempotent
`MERGE` on `knowledge_id` + edges + the `knowledge_text_ft` fulltext write), guards (no
write-back — G6; no env — D-11 is the *registry* consumer's env, not neo4j's), supervision
(restart on-failure, heartbeats, `pending=0` + lexical-leg-non-empty), slice-3 preconditions
(D-12). The §6 guard note is precise about the flag auto-clear's two gates. The network policy
(§3) gives the consumer neo4j at `neo4j:7687` on `fleet-net` — consistent. **Known-safe.**

### (5) Migration feasibility — PASS (F-A6 re-attacked)
The review path is a sequenced cut-over (no double-review window); story/analysis stay additive
(BRPOP atomic); the 2,640-DLQ triage and the 26,877-entry head reset remain bounded (D-12).
Slice 4 now carries the three new guard tests (binary-resolution probe, scope-vocabulary guard,
network-policy guard) — all read-only, nothing to roll back.

### (6) The round-2 new surface — attacked (the three refinements)

**D-16 — the per-step scope model (§5).**
- *Vocabulary closedness:* the vocabulary is a **closed enum of five**; each scope resolves to a
  declared config; the spawn-wrapper's step-1 rejects any scope outside the enum (an undeclared
  scope fails before the socket call). No ad-hoc config is expressible.
- *Validation completeness:* the spawn-wrapper runs **five ordered checks** — (1) scope ∈ vocab,
  (2) phase-authorized for that scope, (3) mounts ⊆ the scope's declared set AND ⊆ the four +
  D-2, (4) network = the scope's network, (5) env = the scope's env — all **before the socket
  call**. No spawn path bypasses them: the resize/drain path (D-14, compose allowlist + mount
  contract) and the phase-spawn path (D-16, the five checks) are the same sibling-spawn wrapper
  (§4).
- *Mount-contract preservation:* every scope's mounts are a subset of `{worktree rw, results
  rw/ro, repo ro, auth ro}` — the scope differences are the results mode, the network, the env,
  and the capabilities, not a fifth mount. The doc-writing scopes write into their *worktree*.
- *No new write path:* the research/review/adversarial/proposal scopes carry "no write flags";
  only `implementation` (the P1-P11 emitters) may, and it is the existing cell execution.
- **Buildability nit (non-falsifying):** the `scope:` field requires a one-field extension to the
  workflow phase spec (the phase dataclass), and the fleet_ladder_plan phases' scope mapping is
  given by example in §5 — the proposal is a plan, so this is declared, not yet implemented, same
  as the neo4j consumer.

**D-17 — the network policy per tier (§3).**
- *Structural soundness:* `fleet-net` contains ONLY the queue redis (6380) + chroma (8000) +
  neo4j (7687) + sonar (9000-9003) + the egress proxy. The portal (8001), the opencode server
  (4096), `finops-redis` (6379), and the host are **not attached** — unreachable by network
  membership, not by a port convention. The queue-isolation invariant (KS-14) is now structural.
- *Egress as the single point:* the egress proxy allowlists ONLY the model endpoints; the
  supervisor/orchestrator ride the same proxy. A compromised cell cannot reach arbitrary hosts —
  the proxy forwards only the model CLIs' traffic.
- **Maintenance nit (non-falsifying):** the model-endpoint allowlist must track provider
  endpoint changes; this is an operational upkeep item, not a structural hole (the policy point
  and its single-egress property are structural).

**D-18 — the binary-attach refinement of D-2 (§4, §7).**
- *Generic-toolchain-only image:* `fleet/base` carries python/node/git/sonar client; the model
  CLIs are NOT baked. The CLIs attach via the auth mounts, and the auth set (D-2) is complete for
  the symlink chain — the `~/.local/bin/claude` symlink AND its `~/.local/share/claude` target,
  plus the `~/.opencode/bin` opencode binary. A broken chain cannot silently degrade: the
  slice-4 **binary-resolution probe** resolves each CLI at container start and **fails loudly**.
- The R1 canonical-env guarantee becomes a boot-time assertion rather than a runtime surprise
  (the F-5 failure class).

### (7) The round-1 revision surface — re-attacked, no regression
D-9 (opencode server operator-side), D-10 (review cut-over), D-11 (kb-registry env), D-13
(supervisor mounts), D-14 (socket/watcher), D-15 (orchestrator env) all re-checked against the
renumbered doc — the resolutions are intact and the mechanisms unchanged; the renumbering moved
sections (§3→§4 image, §4→§6 neo4j, §5→§7 slices, §6→§8 guards) but did not relocate or alter
any closing mechanism. The §9a REVISION LOG section-edited column was re-pointed accordingly.

## VERDICT: SUPPORT

All 7 findings (F-A1…F-A7) are closed; the three operator-refinements (D-16/D-17/D-18) are
edited into the mapping with the mechanism closed by the mapping itself (the scope vocabulary +
spawn-wrapper validation, the network topology + egress proxy, the image/toolchain split +
binary-resolution probe); the guards G1-G6 hold at full strength (the scope model *tightens* G1
by making an undeclared write flag a spawn-time failure); the four constraints hold (the scope
model adds no socket and no fifth mount); the neo4j bridge is intact; the migration is feasible;
and the known-safe list survives (20 → 23 protections). No new finding. The companion
`fleet_ladder_proposal_known_safe.md` is REPLACED with the round-2 known-safe list.

**LOG (p1_reverify round 2, deepseek-v4-pro):** 7/7 findings re-checked CLOSED (mechanism closed
by the mapping, not prose); guards re-traced G1-G6 at full strength; constraints held
(bootstrap-only, no self-activation, socket-orchestrator-only, four-mount contract incl. the
supervisor); neo4j bridge NOT FALSIFIED; migration feasible (review cut-over); the round-2 new
surface (D-16 scope model, D-17 network policy, D-18 binary-attach) attacked — scope vocabulary
closed, spawn-wrapper validation complete (5 ordered checks before the socket), network policy
structurally sound (fleet-net membership, not a port convention), binary-attach symlink-complete
with a fail-loud probe. Two non-falsifying nits noted (the `scope:` schema field; the egress
allowlist upkeep). **SUPPORT** — re-verify committed; awaiting the operator's sign-off.
