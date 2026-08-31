# `quarantine/` — the contamination ledger

`quarantine.jsonl` is the durable, append-only record of work whose output the admission layer
cannot account for. Written by the lease watchdog (`agentic-dynamics supervise leases`), read by
the permanence gate and the analyze/data chain.

**Contaminated ≠ wrong.** It means *unaccounted-for*: produced outside the window the system
reserved for it, so its cost, its provenance, and its place in the grid it belongs to are all
unverified. Contaminated output is never deleted and never silently reused — it is marked, and
the consumers that would otherwise fold it into an aggregate skip it.

## What writes here

`scripts/lease_watchdog.py` sweeps the framework-Redis lease registry each pass and turns every
expired lease into an advisory record:

| Expired lease | What happens |
|---|---|
| **concurrency** | a supervisor flag only — a worker outlived its execution *slot*, which is a throughput problem, not a spend one |
| **budget** | a supervisor flag **and** a quarantine entry against the run's `worktree_identity` and `result_namespace` — the work outlived its *spend reservation*, so what it wrote is unaccounted-for |

Operators can also open and lift entries by hand (`QuarantineReason.MANUAL`). A lift never
rewrites the opening record: both stay on the ledger, so "contaminated for nine days, then
cleared by X because Y" remains legible.

## What reads here

| Consumer | Behaviour on an unreadable ledger |
|---|---|
| `scripts/analyze_worktrees.py` (Game Reports) | **raises** — it publishes aggregates, and "contamination unknown" must never render as "nothing contaminated" |
| `scripts/inventory.py` (the data chain → `data.js`) | **raises**, same reason |
| `scripts/system_snapshot.py` (the permanence gate) | **degrades** — a game board that refuses to render is worse than one that is silent about quarantine |

A *missing* file is an empty ledger (nothing has ever been quarantined). A *corrupt* file is a
loud error. Absent and corrupt are different states and are kept different.

## Surfaces

- **`quarantine.jsonl`** (this directory) — the authority. A plain file, so the analyze chain can
  answer "is this worktree contaminated?" with no Redis, no network, and no daemon running.
- **Redis `finops:quarantine:active`** (framework instance, db 1) — the hot path the Control Room
  board reads, and the surface a containerized cell writes when it cannot reach the host
  filesystem. A mirror that *widens* the file's answer, never a dependency of it.

Rules: `src/agentic_dynamics/control/quarantine.py`.
Watcher: `src/agentic_dynamics/control/lease_watchdog.py`.
Work order: `workflows/repository/admission_leases.yaml` (phase 4).
