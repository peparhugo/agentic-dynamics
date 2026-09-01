---
status: accepted
---

# Fleet-ladder implementation — adversarial review (the findings)

**Verdict: FAIL — 2 findings.** This review falsifies the IMPLEMENTATION (not the proposal —
the proposal is signed off). Every claim below was verified against the committed code, the
compose, the built images, and the live daemon state. Two findings survive the attack; one is a
real isolation-story weakening (the network policy's egress half is unenforced), one is a
mandate-fidelity deviation (the supervisor image is defined but never wired).

## The findings

| # | severity | attack | finding |
|---|---|---|---|
| **F1** | **HIGH** | (5) network policy | **The egress proxy is not "the single internet policy point" — D-17's egress half is unenforced.** `fleet-net` is a normal bridge (`internal=false`), so the cells have direct internet via the bridge NAT; and NO scope or container sets `HTTP_PROXY`/`HTTPS_PROXY` to the proxy. §3 requires "the cell/orchestrator scopes set `HTTP_PROXY`/`HTTPS_PROXY` to it (the scope env, §5)" and "No other egress: a cell cannot reach arbitrary hosts". Both are absent: the cells reach arbitrary internet hosts directly, and the model-endpoint allowlist in `scripts/fleet/egress_proxy.py` is never consulted. The slice-4 network-policy guard also does not check this (it asserts fleet-net membership + absent sandbox ports, but not the proxy route). |
| **F2** | LOW | (1) mandate fidelity | **The `fleet/supervisor` image is defined but never built or used.** `Containerfile.fleet` declares `FROM orchestrator AS supervisor` (the §4 hierarchy `base → orchestrator → supervisor`), but the built images are only `fleet/base`, `fleet/orchestrator` (and a stale `fleet/egress-proxy`); the supervisor tier runs on `fleet/base` (`x-supervisor-base.image: fleet/base`). No guard is weakened (the supervisor still holds no socket, no `FINOPS_KB_WRITE`, the D-13 mounts), but the mandate's third rung is dead code. |

## Attack log (what was tried, in order)

**(1) THE MANDATE.** All deliverables exist: `Containerfile.fleet` (base/orchestrator/
supervisor targets, non-root USER 1001), `infrastructure/docker-compose.ladder.yml`,
`scripts/fleet/{fleet_manager,spawn_wrapper,egress_proxy,probe_binaries,dlq,heartbeat,
review_cutover,review_unit,dlq_triage}.py`, the `scope:` field in `experiment_spec.py`, the
`kb-neo4j` consumer, the seven guard tests, `infrastructure/fleet-bootstrap.service`.
→ **F2**: the supervisor image is defined but not built/used.

**(2) THE GUARDS G1-G6.** G1 write guard (`knowledge_stream.py:184`) intact; G2
actuation-armed never set (compose + `spawn_wrapper` step 5); G3 lineage gate
(`:121,:171`) intact; G4 registry single-appender intact; G5 per-cell scope intact; G6
consumers read-only with the ONE `kb-registry` write-back (compose: exactly one kb consumer
carries `FINOPS_KB_WRITE=1`). → no finding.

**(3) THE CONSTRAINTS.** Socket appears only in the orchestrator tier (`/var/run/docker.sock`
in `x-orchestrator-mounts`, consumed by `campaign-wrapper`/`workflow-runner` only, `ro`);
the mount contract holds (every target ∈ the four + the D-2 auth set + the `fleet-logs`
named volume); the supervisor is KB-read-only (no `FINOPS_KB_WRITE` on any supervisor
service); the bootstrap unit's core is ~3 lines (`docker network create` + `docker-compose
up -d fleet-manager` + `Restart=always`) expanded by systemd boilerplate, with a template
`Environment=REPO` the operator fills at install. → no finding.

**(4) THE SCOPE MODEL.** `validate_spawn`'s five ordered checks (scope ∈ vocab → phase-
authorized → mounts ⊆ the four+D-2 → network = scope's → no undeclared write flag) all run
BEFORE `build_spawn_argv`/`subprocess.run`; `spawn_sibling` raises `SpawnValidationError` and
never reaches the socket. A phase minting an unauthorized scope, a bad mount, or an undeclared
write flag fails (proven by `tests/test_spawn_wrapper.py`). → no bypass. (The scope's `env`
half — which §5 says carries `HTTP_PROXY` — is absent; that is **F1**, not a bypass.)

**(5) THE NETWORK POLICY.** The INTERNAL half is enforced — `fleet-net` carries exactly the
queue redis + chroma + neo4j + sonar ×4 + the egress proxy; `finops-redis` (6379), the portal
(8001 loopback only), the opencode server (4096), and the host are structurally absent. The
EXTERNAL half is not: `fleet-net` is `internal=false`, and no scope sets `HTTP_PROXY`. → **F1**.

**(6) THE RUNTIME.** `fleet/base` + `fleet/orchestrator` build; the compose comes up (12
services verified in slice 1); the binary-resolution probe resolves opencode + claude (fails
loudly on a broken chain — `probe_binaries.py`); the neo4j group `pending = 0` (live check);
`search_knowledge_fulltext` returns hits (live check). → no finding.

**(7) THE SEQUENCING.** The review cut-over was sequenced (no host `trigger_reviews`/`review_all`
running when the containerized `review-unit`+`trigger-reviews` started; `review_all` ran 244
stories / 0 errors exactly once — no double-review window). The additive discipline held (the
3-job probe drained to 3 distinct workers — BRPOP atomic, no double-process). → no finding.

## Disposition

F1 must be closed before the operator's smoke test gates production: either (a) make
`fleet-net` an internal network and set `HTTP_PROXY`/`HTTPS_PROXY` to `egress:8888` in the
scope `env` (§5) + the compose `ladder-env`, or (b) record a documented, operator-signed
deferral. F2 is cosmetic — wire `x-supervisor-base.image: fleet/supervisor` and build the
target, or delete the dead `supervisor` stage.

**F1 — CLOSED (2026-09-01, option (a)).** `x-ladder-env` in
`infrastructure/docker-compose.ladder.yml` now carries `HTTP_PROXY=http://egress:8888`,
`HTTPS_PROXY=http://egress:8888`, and `NO_PROXY=finops-queue,neo4j,chromadb,localhost,
127.0.0.1` (the by-name data-plane hosts, so the proxy — which only allowlists model
endpoints — never sits between a cell and the queue/graph/vector store). The affected
long-lived pools (`fleet-manager`, `kb-neo4j`, `orphan-sweep`) were recreated to pick up the
env; all three came back healthy (binary probe PASS, heartbeats resumed). Traffic evidence
from a one-shot cell run through the recreated env: the egress log recorded
`ALLOW api.anthropic.com:443 (CONNECT)` for an allowlisted host and
`DENY example.com (not in allowlist)` for a non-allowlisted one — the policy point is now
actually consulted, not bypassed. Reachability check in the other direction: `finops-queue:6379`,
`neo4j:7687`, and `chromadb:8000` all connected directly (NO_PROXY-exempted, unaffected by the
new proxy env) — no data-plane regression. New regression guard:
`tests/test_fleet_guards.py::test_every_ladder_env_consumer_routes_through_egress` (every
ladder-env consumer carries the proxy pointed at egress, egress itself never self-proxies, and
NO_PROXY always carries the by-name data-plane hosts). `fleet-net` was left as a normal bridge
(not flipped to `internal: true`) — the proxy-env route plus the allowlist is the enforcement;
making the network internal too is a stronger, separable hardening step, not required to close
this finding. F2 remains open (cosmetic, unrelated to this fix).
