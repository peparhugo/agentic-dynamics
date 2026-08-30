---
status: proposed
---

# The β measurement — the snowball tax (context inflation + the coordination overhead)

**Status: PROPOSED (2026-08-29, operator-directed).** The framework's β parameter — "context
inflation per line, compounding quadratically through the Snowball Rule (N²)" — is
decomposed into TWO measurable faces, and the machine's own ledger already carries a measured
proxy for one of them. The operator's lived observation is the motivating prior: *"Before I
could have 4–5 sessions running at once. Now I'm reduced to 1 workflow because coordination
and breaking the problem down has snowballed out of control due to complexity."* That IS the
N² term's real-world fingerprint. The long-term countermeasure the operator identifies: small,
properly scoped, parallel work distributed across multiple workers — and the fleet ladder's
per-step scope model + the worker pools are the infra that scales it. This design (a) defines
the two measured faces, (b) specifies the coordination-tax instrument + the concurrency-ladder
preregistration, and (c) records the mitigation thesis the ladder operationalizes.

## 1. The two measured faces of β

1. **The per-session context inflation (the token side).** The session token curves across the
   ledger — `sessions.parquet` carries the per-session tokens; the classic N² line growth
   (each added line/unit of context compounds the next session's carry) is directly
   measurable as the token-per-session curve within a workflow's sessions.
2. **The coordination tax (the operator's lived experience).** The overhead of breaking work
   into concurrent units + re-integrating them: the wrapper phases, the merges + conflict
   resolutions, the data-chain serializations, the review churn, the queue waits, the
   operator's own coordination burden. Measured from the machine's own telemetry:

| measured proxy | value | artifact |
|---|---|---|
| the wrapper-phase share of a campaign's spend (single campaign) | **63%** ($0.17 of $0.27 — phases, not cells) | the 2b campaign cost breakdown |
| the concurrency ceiling (lived) | 4–5 concurrent sessions → **1 workflow** as complexity grew | the operator's observation, 2026-08-29 |
| the coordination events per campaign | merges + conflict resolutions + chain runs + review rounds | the session's own record (10+ merges, 3 data-chain rituals in one day) |

## 2. The coordination-tax instrument

**`coordination_overhead(campaign) = (wrapper + merge + chain + review time/cost) / (cell time/cost)`**
— computed per campaign from the ledgers (the wrapper phases' cost vs the cells'), the merge
records (the git history's merge/conflict events per campaign), the chain runs (the
sync/build/manifest events), and the review rounds. The instrument is a measurement rule
([C] — derived from measured fields), reported per campaign and aggregated over the corpus.

## 3. The concurrency ladder (the preregistration sketch)

A campaign-shaped measurement: run the SAME grid at **1 / 2 / 4 / 8 concurrent workflows** and
measure, at each rung: the coordination overhead (per §2), the wall-clock per grid, the
throughput (cells/hour), the coordination events (merges, conflicts, chain waits). The
expected shape: the overhead curve bends up as the concurrency grows (the N² term), with the
operator's lived ceiling (4–5 → 1) as the prior. The output: the **β curve** —
`coordination_overhead(concurrency)` — the measured snowball.

**Pre-registration commitments (per the repo's discipline):** the grid is fixed (a standard
story cell set), the rungs are the four concurrency levels, the concurrency is the only varied
factor, the outcome metrics are fixed (overhead, wall-clock, throughput, coordination events),
the seed is committed, and the ladder runs on the queue machinery (the worker pools' `--scale`).

## 4. The mitigation thesis (recorded for the ladder)

The operator's long-term direction: **small, properly scoped parallel work distributed across
multiple workers** is the β countermeasure — the N² term's growth is bounded by keeping the
units small and their interfaces explicit. The fleet ladder operationalizes it: the **per-step
scope model** (each workflow phase = a sibling container with a closed-scope config — bounded
units with declared interfaces) + the **worker pools** (the per-queue cell containers) + the
**supervisor's coordination** (the fleet manager's watcher/drain — the coordination overhead
itself becomes measured telemetry). The concurrency ladder's curve, measured BEFORE the ladder
and re-measured AFTER (a slice-4-era repeat), is the countermeasure's verification: does the
containerized small-scope parallelism bend the N² curve?

## 5. The sequencing

1. **The instrument** (§2) — a measurement rule over the existing ledgers (no new runs —
   compute the overhead for the corpus's campaigns immediately).
2. **The concurrency ladder** (§3) — the preregistration + the campaign (the deepseek
   envelope, ~4 rungs × the standard grid).
3. **The re-measurement** — after the fleet ladder's slice 1 (the worker pools live) and
   slice 2 (the per-step scopes): the ladder repeat of the concurrency curve.
4. Each bounded, with the tests (the instrument's arithmetic verified against a known
   campaign) and the rollback (the instrument is read-only).

## 6. Guard

The two faces are measured, never blended: the context-inflation curve cites the session token
fields; the coordination tax cites the wrapper/merge/chain/review fields. The ladder's
pre-registered commitments fix the grid, the rungs, and the outcomes — a deviation is a FAILED
finding. The operator's lived ceiling is recorded as the prior [H], never as a measurement.
The mitigation thesis is a thesis [P] until the ladder's re-measurement bends the curve.

**LOG:** β decomposed into the two measurable faces (the session-token curves + the
coordination tax); the measured proxies cited (2b's 63% wrapper share, the operator's lived
concurrency ceiling); the coordination-tax instrument defined; the concurrency-ladder
preregistration sketched (1/2/4/8-wide, fixed grid, committed seed); the mitigation thesis
recorded (the small-scoped parallel units + the ladder's scope model + worker pools as the N²
countermeasure, verified by the ladder's re-measurement); the sequencing; the guard.
**PROPOSED — the instrument is immediately computable; the ladder is the countermeasure.**
