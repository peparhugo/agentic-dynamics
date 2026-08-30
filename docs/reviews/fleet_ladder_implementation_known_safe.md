---
status: accepted
---

# Fleet-ladder implementation — known-safe list (the attacks that passed)

**Verdict: the attacks that passed are SUPPORT.** This is the complement of
`fleet_ladder_implementation_adversary.md` (the FAIL findings F1/F2 live there). Everything
below was attacked and held — verified against the committed code, the compose, the built
images, and the live daemon state on 2026-08-30.

## Known-safe (verified, not falsified)

- **The isolation story's three other pillars hold.** The mount contract (every mount target ∈
  the four + the D-2 auth set + the `fleet-logs` named volume), the scope model (the closed
  five-scope vocabulary + the five-check validation), and the non-root user (USER 1001, uid ==
  the host user) are intact and enforced. Only the network policy's egress half is open (F1).

- **The socket appears in exactly ONE tier.** `/var/run/docker.sock` is mounted `ro` only by
  the orchestrator services (`campaign-wrapper`, `workflow-runner`) via `x-orchestrator-mounts`;
  the cell and supervisor tiers hold none (guard 1 + live grep).

- **The supervisor is KB-read-only.** No supervisor service carries `FINOPS_KB_WRITE`; the
  orchestrator never carries it at the container level (D-15 — its F-1/F-2/P11 writes authorize
  in code); exactly one kb consumer (`kb-registry`) carries it (D-11).

- **G1-G6 are re-traced and intact.** G1 write guard, G2 actuation-armed (never set), G3
  lineage (`causes`→observation), G4 registry single-appender, G5 per-cell scope, G6 consumer
  read-only (single `kb-registry` exception) — all present in the code and the compose.

- **The spawn-wrapper's five checks are not bypassable.** A scope outside the vocabulary,
  an unauthorized scope, a bad mount, a network mismatch, or an undeclared write flag each
  fails validation BEFORE any `docker`/socket call (30 unit tests in
  `tests/test_spawn_wrapper.py`, all passing).

- **The internal network isolation holds (D-17's internal half).** `fleet-net` membership is
  exactly the queue redis (6379 in-network), chroma, neo4j, sonar ×4, and the egress proxy;
  `finops-redis` (6379), the Control Room portal (8001 — loopback-only publish), the opencode
  web server (4096), and the host are structurally absent from the cells' reachability.

- **The runtime probes pass.** `fleet/base` + `fleet/orchestrator` build; the compose comes up;
  the binary-resolution probe resolves opencode (1.18.15) + claude (2.1.228) at container start
  and fails loudly on a broken chain; the neo4j group `pending = 0`; the RRF lexical leg returns
  real hits (`search_knowledge_fulltext` non-empty over `knowledge_text_ft`).

- **The sequencing held.** The review path cut over without a double-review window (host
  `trigger_reviews`/`review_all` stopped/drained before the containerized path started;
  `review_all` ran exactly once). The additive discipline held (BRPOP-atomic distribution —
  3 probe jobs → 3 distinct workers, no double-process).

- **The full deterministic suite is green.** `python3 -m pytest tests/ -m "not external" -q`
  → 2201 passed, 0 failed (116 external deselected for the operator's smoke test).

- **The data chain is current.** `scripts/reproduce.sh` re-derived the parquet, the 8 canonical
  lab artifacts, `data.js`, and the manifest from the current corpus; the README "By the
  Numbers" figures match `public_statistics`.

## Notes (not findings)

- The systemd bootstrap's "~3-line" core (`docker network create fleet-net` +
  `docker-compose up -d fleet-manager` + `Restart=always`) is expanded by mandatory systemd
  boilerplate; the `Environment=REPO` value is a documented install-time placeholder.
- The `kb-neo4j`/`kb-chroma`/`kb-ledger` consumers run the binary probe unnecessarily (they
  invoke no CLI); harmless — the probe passes via the auth mounts.
- The orchestrator's `--orchestrator` sibling-spawn path is implemented and unit-tested but has
  not been exercised end-to-end against the socket — that is the operator's smoke test (slice 7).
