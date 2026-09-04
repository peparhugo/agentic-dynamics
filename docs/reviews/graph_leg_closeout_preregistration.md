---
status: accepted
kind: preregistration
spec: graph_leg_closeout
phase: p0_pin_threads
run: run-57b8ec179e30
generated_at: 2026-09-04T02:52:00Z
---

# Preregistration — `graph_leg_closeout` (p0_pin_threads)

**The house pin convention.** This document is written BEFORE any implementation phase of the
wave executes (`a1_fix_idle_exit`, `c1_assoc_edge_design`, `b1_prune_expansion_rels`,
`b2_probe_warning_free`, `a2_verify_daemon_survives_idle`, `c2_assoc_edge_writer`,
`c3_assoc_probe`, `g9_adversarial`, `g10_test_gate`). Its purpose is twofold, and both halves
are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the premises, do not assert them.** The three threads this wave exists to close are
   stated as current-state claims in the spec's `question`/`context.finding` block (authored
   2026-09-04 from the session close record): (1) the kb_worker idle-exit footgun (a daemon
   exits 0 after 12 empty polls); (2) the expansion-leg schema noise
   (`ALLOWED_EXPANSION_RELS` names rels nothing ever creates, and the live neo4j warns per
   query); (3) the associative layer — Knowledge records are LEAF nodes, only the multi-label
   code symbols carry edges, and finding→code/spec edges are never written. This phase
   re-derives each edge against the actual code AND the live graph at the machine-local state,
   and records the commands that produced the evidence, so a reader can reproduce every finding
   without trusting this document. **An edge that does not hold is a FAILED finding.** If a
   claim could not be reproduced after THREE attempts, the deviation was to be recorded and the
   claim FAILED — never looped.

No claim below was accepted on the spec's authority. Every edge was verified with a live probe
at `2026-09-04T02:45–02:52Z`, against the code at the worktree HEAD and the machine-local graph
+ control state at the main checkout. All three edges **PASS** — each reproduced the spec's
current-state claim with measured evidence, with the nuances (AFFECTS, the 18.3k census figure)
recorded as deviations in §4. The evidence is quoted so the adversarial phase (g9) can re-run
every probe.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path (executed) | `/home/drseuss/ai-finops-framework/workflows/repository/graph_leg_closeout.yaml` (machine-local, at the MAIN checkout) |
| Spec **SHA256** | `4c0633bf305df230d3767a0cfa2965ec0453dc1576b571eae503260785993537` |
| Spec size | 23,680 bytes |
| Spec `workflow_revision_id` | `a2d2e01c1672a90cd12759b92413308e83081553d13a4cacc0cb2d2ed643dd09` — equals the running run's recorded revision (control db `runs.workflow_revision_id`) |
| Worktree HEAD (git sha) | `96738e6da3a1a30e58f426ee7ce98afb6a32305b` (branch `feature/graph-leg-closeout`, worktree `/tmp/wt_graph_leg_closeout`) |
| Main checkout HEAD | `96738e6da3a1a30e58f426ee7ce98afb6a32305b` (`main`, `/home/drseuss/ai-finops-framework`) — the machine-local state host |
| src/ parity | identical — `sha256sum` of `graph.py` + `kb_worker.py` match byte-for-byte across the worktree and the main checkout (see §6 reproduce) |
| Run (this phase) | `run-57b8ec179e30` — `graph_leg_closeout`, `state: running`, started `2026-09-04T02:45:01.207371Z`, model `deepseek/deepseek-v4-flash`, control epoch 229 |
| Prior p0 attempt | `run-6acdf9a56650` (ledger `experiments/results/workflows/graph_leg_closeout/20260904T024222Z.json`) — sonnet-5, `exit_code=1`, 0 tokens/0 cost (spawn failure); this run is the re-run |
| DB location (per mandate) | control db + Redis 6380 at the MAIN checkout (`/home/drseuss/ai-finops-framework/experiments/results/control/control.db`, Redis 6380 db 2); the graph census reads the LIVE neo4j (bolt, neo4j 5.26.29) |
| Goal prefix | `close the graph-leg open threads on feature/graph-leg-closeout: kb_worker daemon idle-exit fix, expansion-leg allowlist prune, associative-layer first-family design and writer` |
| Pinned at | 2026-09-04T02:52:00Z |

Reproduce the pin — these are the EXACT bytes the run executes:

```bash
sha256sum workflows/repository/graph_leg_closeout.yaml   # at the main checkout
# 4c0633bf305df230d3767a0cfa2965ec0453dc1576b571eae503260785993537
git rev-parse HEAD          # in the executing worktree /tmp/wt_graph_leg_closeout
# 96738e6da3a1a30e58f426ee7ce98afb6a32305b
python3 -c "import sys; sys.path.insert(0,'src'); \
from agentic_dynamics.experiment.experiment_spec import load_spec; \
print(load_spec(__import__('pathlib').Path('workflows/repository/graph_leg_closeout.yaml')).workflow_revision_id)"
# a2d2e01c1672a90cd12759b92413308e83081553d13a4cacc0cb2d2ed643dd09
```

If either value differs when g9 (adversarial) or g10 (test gate) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed. **The spec
file is UNTRACKED at the main checkout** (`?? workflows/repository/graph_leg_closeout.yaml`) and
is absent from the worktree — it is the controller-authored mandate that drives this run, not a
committed file. Re-pins must hash the same machine-local path (see D-3).

**Spec shape at the pin** — ten phases, all `kind: agent` except the terminal `g10_test_gate`
(`kind: test`):

| # | Phase | kind | scope | run_model |
|---|---|---|---|---|
| 0 | `p0_pin_threads` | agent | implementation | (main) |
| 1 | `a1_fix_idle_exit` | agent | implementation | (main) |
| 2 | `c1_assoc_edge_design` | agent | implementation | (main) |
| 3 | `b1_prune_expansion_rels` | agent | implementation | (main) |
| 4 | `b2_probe_warning_free` | agent | implementation | (main) |
| 5 | `a2_verify_daemon_survives_idle` | agent | implementation | (main) |
| 6 | `c2_assoc_edge_writer` | agent | implementation | (main) |
| 7 | `c3_assoc_probe` | agent | implementation | (main) |
| 8 | `g9_adversarial` | agent | adversarial_readonly | deepseek/deepseek-v4-pro |
| 9 | `g10_test_gate` | test | implementation | (main) |

---

## 2. Verified current-state edges (re-derived against code + the live graph)

Each edge is stated as the spec's `question`/`context.finding` claims it, then **independently
re-derived**. The verdict legend is stated up front so no status is misread:

- **PASS** — the mandate's claim describes the state measured at the pin. The gap the wave was
  built to close is OPEN, verified with code + live evidence. In a first-run pin this is the
  expected, positive result: it confirms the wave is targeting real state, not asserted state.
- **FAILED** — the mandate's claim does not hold as stated. Recorded with the deviation and the
  true state, per the "an edge that does not hold is a FAILED finding" rule.

Every probe below ran read-only (`MATCH`/`RETURN`/`count` only on neo4j; `XINFO` on Redis;
`grep`/`sed`/`sha256sum`/`git rev-parse` on code) from the machine-local host at the main
checkout unless noted.

### Edge 1 — IDLE-EXIT: the daemon self-exits 0 on idle; `--once` is safe (`scripts/kb_worker.py`)

*Claim.* `scripts/kb_worker.py:714` — a daemon-mode worker (no `--once`) exits 0 after
`IDLE_POLLS_BEFORE_EXIT=12` consecutive empty polls (`:80`, `:702-715`); `--once` breaks at
`:712` before the idle check ever fires.

*Method.*

```bash
sed -n '77,81p'  scripts/kb_worker.py    # the constant
sed -n '638,645p' scripts/kb_worker.py   # --once arg definition
sed -n '670,674p' scripts/kb_worker.py   # empty_polls init
sed -n '699,718p' scripts/kb_worker.py   # poll bookkeeping / --once break / idle-exit break
```

*Evidence.*

```
77: REDIS_BASE_DELAY = 2.0
78: REDIS_MAX_RETRIES = 10
79: BLOCK_TIMEOUT_MS = 10_000
80: IDLE_POLLS_BEFORE_EXIT = 12
81: RECONCILE_EVERY_S = ks.RECONCILE_INTERVAL_S

638: def main() -> None:
639:     parser = argparse.ArgumentParser(description="Run a knowledge-base consumer group")
...
644:     parser.add_argument("--once", action="store_true", help="process one batch then exit")
645:     args = parser.parse_args()
...
672:     empty_polls = 0
673:
674:     while True:

699:         processed = outcome.processed
700:         processed_total += processed
701:         if processed == 0:
702:             empty_polls += 1
703:         else:
704:             empty_polls = 0
...
712:         if args.once:
713:             break
714:         if empty_polls >= IDLE_POLLS_BEFORE_EXIT:
715:             log(f"idle after {empty_polls} polls; exiting")
716:             break
717:
718:     log(f"Done. processed={processed_total}")
```

The structure reproduces the claim exactly:

- `IDLE_POLLS_BEFORE_EXIT = 12` at `:80`.
- `empty_polls` starts 0 at `:672` (before the loop at `:674`); each `process_batch` whose
  `outcome.processed == 0` increments it, any non-empty poll resets it (`:701-705`). Each empty
  poll is a full `BLOCK_TIMEOUT_MS` = 10 s read (`:79`).
- The **`--once` break fires first** at `:712` — after the single batch the loop exits whether
  the poll was empty or not, so the idle check at `:714` is unreachable in `--once` mode
  (one-batch-then-exit, exit 0).
- A **daemon (no `--once`)** reaches `:714`; after the 12th consecutive empty poll the
  `"idle after 12 polls; exiting"` branch (`:715`) breaks the loop, `main()` falls through to
  `:718` and returns normally — **exit 0**. There is no `sys.exit(nonzero)` anywhere in `main`
  and no exception path in the idle case (the `ConnectionError`/generic handlers at `:677-692`
  `continue`, they do not exit).

**PASS** — the idle-exit footgun is exactly as the spec's Thread 1 states: a caught-up daemon
self-exits 0 after 12 consecutive empty polls (~2 minutes of quiet at the 10 s block timeout),
so a `restart:on-failure` supervisor (which only restarts failures) leaves it dead; `--once`
is unaffected. The fix is Thread 1's `a1` deliverable.

### Edge 2 — EXPANSION NOISE: the allowlist names rels with no writer, and the expansion emits them (`knowledge/graph.py`)

*Claim.* `knowledge/graph.py:40-60` — the full `ALLOWED_EXPANSION_RELS` set; names with NO
writer exist (spec expects CONTRADICTS/PRECEDES/PRODUCED_BY/AFFECTS); the expansion query emits
them (`expand_candidates` / `IMPACT_EXPANSION_RELS`); the live neo4j warns per query for the
names nothing ever creates.

*Method — full set + the expansion emission.*

```bash
sed -n '40,60p' src/agentic_dynamics/knowledge/graph.py          # the two allowlists
sed -n '1114,1130p; 1180p' src/agentic_dynamics/knowledge/graph.py  # the query emits the union
# writer census: for each allowlisted name, every MERGE/create of that rel type in src/ + scripts/
```

*Evidence — the full sets (the frozenset literal at `graph.py:40-53`; `IMPACT_EXPANSION_RELS`
at `:60`).*

```python
ALLOWED_EXPANSION_RELS = frozenset(           # graph.py:40-53 — 10 names
    {"DEFINES", "IMPORTS", "CALLS", "TESTED_BY", "PRODUCED_BY", "PRECEDES",
     "SUPERSEDES", "CONTRADICTS", "CONTAINS", "AFFECTS"})
IMPACT_EXPANSION_RELS = frozenset(ALLOWED_EXPANSION_RELS - {"SUPERSEDES"})   # :60 — 9 names
```

Sorted (the union string the expansion interpolates): `AFFECTS | CALLS | CONTAINS |
CONTRADICTS | DEFINES | IMPORTS | PRECEDES | PRODUCED_BY | SUPERSEDES | TESTED_BY`.
`expand_candidates` defaults to the full allowlist — `rels = "|".join(sorted(rels or
ALLOWED_EXPANSION_RELS))` (`graph.py:1180`) — and hands it to `_neighbors`, which interpolates
it into `MATCH (n)-[r:{rels}]-(m) ...` (`graph.py:1126`). `IMPACT_EXPANSION_RELS` (`:60`) is the
same set minus `SUPERSEDES` and is passed by the impact traversal (`evidence_analyzer`), so BOTH
expansion callers emit the writer-less names. Verified live: an `expand_candidates` probe over a
real code symbol emitted `MATCH (n)-[r:AFFECTS|CALLS|CONTAINS|CONTRADICTS|DEFINES|IMPORTS|PRECEDES|PRODUCED_BY|SUPERSEDES|TESTED_BY]-(m) ...`.

*Evidence — the writer census (grep of every rel name against `src/` + `scripts/`).*

| Rel | Writer(s) | Census result |
|---|---|---|
| `DEFINES` | `graph.py:914` — `populate_versioned_graph`: `MERGE (m)-[:DEFINES]->(s)` (ModuleVersion→SymbolVersion) | WRITTEN |
| `IMPORTS` | `graph.py:792` (legacy `load_codebase_graph` CodeModule→CodeModule), `graph.py:931` (versioned ModuleVersion→ModuleVersion) | WRITTEN |
| `CALLS` | `graph.py:946` — `populate_versioned_graph`: `MERGE (a)-[:CALLS]->(b)` (SymbolVersion→SymbolVersion) | WRITTEN |
| `TESTED_BY` | `graph.py:970` — `populate_versioned_graph` test-module rule | WRITTEN |
| `SUPERSEDES` | `graph.py:1036` (versioned entity lineage), `kb_worker.py:472` (kb-neo4j handler, Knowledge→Knowledge on `operation=supersede`) | WRITTEN |
| `CONTAINS` | `graph.py:878` (Revision→ModuleVersion), `graph.py:913` (ModuleVersion→SymbolVersion) | WRITTEN |
| `AFFECTS` | **conditional** — `graph.py:990`/`:1008` write `SonarIssue`/`Diagnostic` → `AFFECTS` → `SymbolVersion`, but ONLY when `populate_versioned_graph(..., issues=, diagnostics=)` is passed them; the params default `None` (`:813-814`) and **no call site supplies them** (`evidence_analyzer.py:276`, `graph_family_build.py:120` + `:283`, `tests/test_versioned_graph.py:70` all omit) | DORMANT — a writer exists, nothing feeds it; **zero live edges** |
| `PRODUCED_BY` | none anywhere (only the retrieval weight `retrieval.py:96` + the allowlist) | NO WRITER |
| `PRECEDES` | none anywhere (only the retrieval weight `retrieval.py:97`) | NO WRITER |
| `CONTRADICTS` | none anywhere (only the retrieval weight `retrieval.py:99` + `CONFLICT_RELATIONSHIPS` at `retrieval.py:102`) | NO WRITER |

So the true no-writer set is **PRODUCED_BY, PRECEDES, CONTRADICTS** (no writer anywhere in the
codebase), plus **AFFECTS** as a dormant case (a writer exists but no call site feeds it and the
live graph holds zero AFFECTS edges — see Edge 3's census). The spec expected all four of
CONTRADICTS/PRECEDES/PRODUCED_BY/AFFECTS to be writer-less; three hold exactly and AFFECTS holds
empirically (zero edges) but not in the code sense — recorded as D-1. The writer census also
surfaced the mirror case: `kb_worker.py:472` additionally writes `CLEARED_BY`/`REPLACED_BY`
(cross-entity tombstone edges) which are NOT in the allowlist — not part of this prune, but g9
should not confuse the two directions.

*Evidence — the live neo4j warning (the noise the spec's Thread 2 names).* Neo4j 5.26.29 returns
one server notification per query for each allowlisted rel type with **no relationship type
token** in the database:

```
code:        Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning
description: "One of the relationship types in your query is not available in the database,
              make sure you didn't misspell it ... (the missing relationship type is:
              CONTRADICTS)"      # also emitted for PRECEDES and PRODUCED_BY on the SAME query
```

The probe's single `_neighbors`-shape query (the exact union string above) produced **3
server warnings — CONTRADICTS, PRECEDES, PRODUCED_BY**. `AFFECTS` did NOT warn: its rel-type
token exists in the store (registered by the dormant writer on some past populate) despite zero
live edges. Every real expansion query that carries the default allowlist (i.e. the retrieval
leg's `expand_candidates`) emits this warning set per hop.

**PASS** — `ALLOWED_EXPANSION_RELS` names rels nothing creates, the expansion query emits all of
them (`expand_candidates` default + `IMPACT_EXPANSION_RELS`), and the live server warns per
query for CONTRADICTS/PRECEDES/PRODUCED_BY. The prune (`b1`) target set is
`{PRODUCED_BY, PRECEDES, CONTRADICTS}` unconditionally, with AFFECTS decided by the `c1` design
per hard rule (2) — never prune a name c1 claims; if unclaimed, AFFECTS is prunable (dormant
writer, zero edges).

### Edge 3 — LEAF NODES: Knowledge records are leaves; only multi-label code symbols carry edges; zero finding/session/verdict → code/spec edges

*Claim.* Knowledge records (wave findings/sessions/verdicts) are LEAF nodes; only the
multi-label code symbols carry edges (CALLS/TESTED_BY/SUPERSEDES 18.3k); finding→code/spec
edges are never written, so the graph leg's distinctive value beyond fulltext awaits the design
item.

*Method — the read-only census against the LIVE kb-neo4j leg* (the compose service's bolt port,
published at `localhost:7687`; `neo4j:7687` resolves only inside the compose network — the same
store; see D-4). Consumer-state check first (the census reads a caught-up projection):

```bash
python3 -c "import redis,json; r=redis.Redis(port=6380,db=2); \
[print(json.dumps({k.decode() if isinstance(k,bytes) else k: v for k,v in g.items()}, default=str)) \
 for g in r.xinfo_groups('kb:v1:changes')]"
# kb-neo4j-v1: consumers=35  pending=0  lag=0  entries-read=39991  (stream length 39,812)
```

Then the label / edge / leaf census over the `Neo4jClient` vocabulary (every statement a
`MATCH`/`RETURN` — read-only).

*Evidence — node census.*

```
['Knowledge', 'SymbolVersion'] : 32,001     # the multi-label code symbols (populate_versioned_graph
                                            #   does SET s:Knowledge on SymbolVersion, graph.py:892)
['Knowledge']                   :  4,192     # knowledge-only records (the candidate LEAF population)
['ModuleVersion']               :  4,098     # NOT :Knowledge (no multi-label join on modules)
['Step']                        :  2,435     ['Revision']: 281   ['CodeModule']: 244
['Session']                     :    222     ['ExperimentRun']: 449   ...
['SonarIssue']                  :      1     # present, but ZERO AFFECTS edges (see below)
```

*Evidence — the edge census (all rel types, then restricted to code-symbol endpoints).*

```
ALL edges:          CONTAINS 36,099 | DEFINES 32,001 | TESTED_BY 9,685 | CALLS 5,394
                    | SUPERSEDES 3,958 | HAS_STEP 2,435 | NEXT 2,213 | IMPORTS 565
                    | RUN_ON 435 | TOUCHED 272 | CLASSIFIED_AS 260 | IMPORTED_BY 214
                    | INSTANCE_OF 73 | PROFILE_IN 10 | HAS_BASIN 8        # NO others
code-symbol ends:   CONTAINS 32,001 | DEFINES 32,001 | TESTED_BY 9,685 | CALLS 5,394
                    | SUPERSEDES 3,958 | IMPORTS 351
```

The graph holds edges ONLY between code-structure nodes (`ModuleVersion`/`SymbolVersion`, plus
the legacy `CodeModule`/`Revision` graph and the experiment/session layers). The named
CALLS/TESTED_BY/SUPERSEDES edges measure **5,394 + 9,685 + 3,958 = 19,037** at the pin (the
close record's "18.3k" was measured on an earlier/smaller corpus — D-2). Zero AFFECTS edges
live, confirming the Edge-2 dormant-writer finding. Zero PRODUCED_BY/PRECEDES/CONTRADICTS edges
live, confirming the no-writer finding.

*Evidence — the Knowledge-only records are ALL leaves.*

```
MATCH (n:Knowledge) WHERE NOT (n:SymbolVersion OR n:ModuleVersion)
OPTIONAL MATCH (n)-[r]-(m) WITH n, count(r) AS deg WHERE deg = 0
RETURN source_type, count(*)            # leaf Knowledge-only nodes by source_type:

  code 2,155 | finding 1,294 | story 302 | review 242 | spec 78 | policy 71
  | meta_session 30 | actuation 11 | report 4 | reflection 3 | decision 1 | wave_verdict 1
                                        # TOTAL = 4,192 == the full knowledge-only count
```

Every one of the 4,192 knowledge-only records has **degree zero** — the stronger form of the
leaf claim. The "does ANY knowledge-only node carry ANY edge to a code/spec node?" probe
(endpoints `SymbolVersion`/`ModuleVersion`/`CodeModule`/`Revision`) and the "knowledge-only
nodes that DO have any edges" probe both return **empty**.

*Evidence — zero finding/session/verdict → code/spec edges.*

```
finding 1,294 nodes, edges_out_of_family = 0
meta_session 30 nodes (the session family), edges_out_of_family = 0
wave_verdict 1 node, edges_out_of_family = 0
review 242 / story 302 / report 4 / policy 71 / spec 78 nodes, edges_out_of_family = 0 (each)
```

**PASS** — Knowledge records (findings, sessions/meta_session, verdicts/wave_verdict, reviews,
policies, specs) are leaf nodes; only the multi-label `SymbolVersion:Knowledge` code symbols
carry edges; the measured CALLS/TESTED_BY/SUPERSEDES total is 19,037; and there are **zero**
finding/session/verdict → code/spec edges of any type. The associative-layer gap (Thread 3) is
verified open exactly as the spec's `context.finding` states it, ready for `c1`'s first-family
decision.

---

## 3. Preregistered run criteria (what the later phases owe)

The p0 mandate is a pin; the wave's proof criteria are preregistered here per the spec's hard
rules so g9/g10 can be measured against fixed targets rather than asserted after the fact:

| Criterion (hard rule) | Measured at p0 pin | Target after the wave |
|---|---|---|
| (1) daemon never self-exits on idle; `--once` one-batch-then-exit | **daemon exits 0 after 12 empty polls** (Edge 1 PASS — `:714-716` break, `:718` return); `--once` breaks at `:712` first | a1: daemon with 12+ empty polls keeps polling (bounded-run test asserts it); `--once` still one batch then exit 0; test_gate in g10 |
| (2) `ALLOWED_EXPANSION_RELS` == writers ∪ c1-claims | **10 names; no-writer set PRODUCED_BY/PRECEDES/CONTRADICTS + dormant AFFECTS** (Edge 2 PASS — per-query `UnknownRelationshipTypeWarning` for the three live) | b1: dead names pruned from the allowlist + `IMPACT_EXPANSION_RELS` + the query's rel patterns in one place; frozen allowlist test; b2: expansion runs warning-free on the live leg |
| (3) Knowledge leaf nodes gain their first real edges | **4,192 knowledge-only records, all degree 0; zero finding→code/spec edges** (Edge 3 PASS) | c1 names one family (target addressing + rel name + writer site + provenance); c2 writes it idempotently, best-effort; c3 probe shows a real record's node carrying the chosen edge and the leaf count dropping |

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each is either an expected first-run property or a
measured nuance a later phase must consume; none is a FAILED edge.

**D-1 — AFFECTS is dormant, not writer-less.** The spec's `context.finding` and the p0 prompt
expect CONTRADICTS/PRECEDES/PRODUCED_BY/AFFECTS to be "names nothing ever creates". The code
census shows a real AFFECTS writer at `graph.py:990`/`:1008` (`populate_versioned_graph`'s
`issues`/`diagnostics` params) — but no call site in the codebase passes those params
(`evidence_analyzer.py:276`, `graph_family_build.py:120`/`:283`, `tests/test_versioned_graph.py:70`),
so it is never fed. Empirically AFFECTS has zero live edges and its token exists (no neo4j
warning), so it behaves as a dead name without being a code-absent one. **b1 decision input:**
prune PRODUCED_BY/PRECEDES/CONTRADICTS unconditionally; treat AFFECTS per c1 — if c1 claims no
allowlisted name for the first family, AFFECTS is a prune candidate (dormant writer, zero edges,
never fed); the "never prune a name c1 claims" rule is the only thing that keeps a claimed name.

**D-2 — the census figure has moved: "18.3k" → 19,037.** The close record's `CALLS/TESTED_BY/
SUPERSEDES 18.3k` measured an earlier corpus. At this pin the same three rel types measure
5,394 + 9,685 + 3,958 = **19,037** edges among code-symbol endpoints (the kb-neo4j consumer is
caught up, so this is the current true count, not a lag artifact). The structure the claim
establishes is unchanged — edges exist only among code-structure nodes, Knowledge records are
leaves. g9 should census, never assert a fixed row count.

**D-3 — the executed spec is an untracked machine-local file, not a committed one.** The spec
that drives this run lives at `/home/drseuss/ai-finops-framework/workflows/repository/
graph_leg_closeout.yaml`, is `??` (untracked) in the main checkout, and is absent from the
branch. Its content hash computes to the run's recorded `workflow_revision_id`
(`a2d2e01c…`), which is how the pin anchors it to the executing mandate. A re-pin must hash the
same machine-local path; the branch gains the spec only if the controller commits it as part of
the permanence decision.

**D-4 — the graph census connected at `localhost:7687`, not the compose-internal `neo4j:7687`.**
From the orchestrator/host shell `neo4j` does not resolve (the name is compose-network-scoped);
the container's published bolt port is the same store at `localhost:7687` (neo4j 5.26.29, the
live kb-neo4j projection — kb-neo4j-v1 pending 0 / lag 0). The graph module resolves this by env
(`FINOPS_NEO4J_URI`, default `bolt://localhost:7687`, `graph.py:210-212`); an in-container g9
probe may use the name form — the store is identical.

---

## 5. Scope compliance

The phase mandate (p0 prompt): write this preregistration carrying the pin + the three verified
edges, then commit with the `[workflow] p0_pin_threads — <goal prefix>` subject.

- **Created/rewritten:** `docs/reviews/graph_leg_closeout_preregistration.md` (this file) — the
  pin for this run.
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `sed`, `grep`, a read-only registry/control-db read, `XINFO GROUPS` on Redis, and `MATCH`/
  `RETURN`-only census queries against the live neo4j. No graph writes, no KB writes, no
  publishes, no flushes, no mutations.
- **Not done, deliberately:** the code anchors (`kb_worker.py:714`, `graph.py:40-60`) were left
  unrepaired — they are the wave's own `a1`/`b1` targets, and editing them here would defeat the
  pin. The throwaway census script ran from `/tmp` (outside the repo); no artifacts were written
  into the worktree beyond this file.

---

## 6. Reproduce the evidence

```bash
# pin
sha256sum /home/drseuss/ai-finops-framework/workflows/repository/graph_leg_closeout.yaml
git -C /tmp/wt_graph_leg_closeout rev-parse HEAD
# src parity (worktree vs main checkout — identical bytes at the pin)
sha256sum src/agentic_dynamics/knowledge/graph.py scripts/kb_worker.py
sha256sum /tmp/wt_graph_leg_closeout/src/agentic_dynamics/knowledge/graph.py /tmp/wt_graph_leg_closeout/scripts/kb_worker.py
# Edge 1 (code)
sed -n '77,81p; 638,645p; 670,674p; 699,718p' scripts/kb_worker.py
# Edge 2 (code)
sed -n '40,60p' src/agentic_dynamics/knowledge/graph.py
grep -rn 'MERGE.*:\(PRODUCED_BY\|PRECEDES\|CONTRADICTS\|AFFECTS\)' src/ scripts/   # writer census
sed -n '1122,1130p; 1180p' src/agentic_dynamics/knowledge/graph.py               # the rel-union emission
# Edge 2 (live) + Edge 3 (live census): the Neo4jClient vocabulary, read-only
python3 /tmp/graph_leg_census.py        # from the main checkout, src on path (MATCH/RETURN only)
# Edge 3 (consumer state)
python3 -c "import redis,json; r=redis.Redis(port=6380,db=2); [print(g) for g in r.xinfo_groups('kb:v1:changes')]"
```

---

## 7. Verdict

| # | Mandate edge (as stated) | Status at launch |
|---|---|---|
| 1 | IDLE-EXIT — daemon exits 0 after 12 empty polls (`:714`); `--once` breaks at `:712` first | **PASS** — `:80` constant, `:701-705` bookkeeping, `:712` `--once` break precedes `:714` idle break, `:718` return = exit 0; the daemon self-exits under `restart:on-failure` |
| 2 | EXPANSION NOISE — allowlist names rels with no writer; the expansion emits them | **PASS** — 10-name allowlist; no-writer set PRODUCED_BY/PRECEDES/CONTRADICTS (+ dormant AFFECTS, D-1); `expand_candidates` default + `IMPACT_EXPANSION_RELS` emit all; live neo4j returns `UnknownRelationshipTypeWarning` per query for the three |
| 3 | LEAF NODES — Knowledge records are leaves; code symbols carry the edges; zero finding→code/spec | **PASS** — 4,192 knowledge-only records all degree 0 (finding 1,294 / meta_session 30 / wave_verdict 1 …); CALLS+TESTED_BY+SUPERSEDES = 19,037 among code symbols; zero finding/session/verdict → code/spec edges of any type |

**p0 verdict: all three mandate edges PASS — every open gap this wave exists to close is
verified open at the pin, with code + live-graph evidence, none asserted.** This is the expected
first-run result: the wave targets real, measured state. The preregistered targets in §3 give
a1/b1/c1 fixed criteria to invert, and the D-series notes give b1 (AFFECTS vs the prune set)
and g9 (census, not asserted counts; the spec file is untracked) the distinctions they must not
conflate. The mandate is anchored: spec SHA256
`4c0633bf305df230d3767a0cfa2965ec0453dc1576b571eae503260785993537`
(`workflow_revision_id a2d2e01c…`) at worktree git `96738e6da3a1a30e58f426ee7ce98afb6a32305b`,
machine-local graph/control state at the main checkout (`96738e6da`). `a1_fix_idle_exit` may
proceed.
