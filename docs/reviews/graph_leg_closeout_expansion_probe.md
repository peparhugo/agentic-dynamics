---
status: accepted
kind: evidence
spec: graph_leg_closeout
phase: b2_probe_warning_free
run: run-57b8ec179e30
generated_at: 2026-09-04T03:10:00Z
---

# graph_leg_closeout — expansion-query warning probe (b2)

**Live verification, read-only, that the b1 prune stopped the expansion query from emitting
unused-rel warnings.** Evidence captured 2026-09-04 against the LIVE kb-neo4j leg (the compose
`kb-neo4j` service's published bolt port, `bolt://localhost:7687` — same store as
`bolt://neo4j:7687`, in-container name form; kb-neo4j-v1 consumer lag 0 / pending 0 at probe
time). Every probe is a `MATCH`/`RETURN` — no writes, no schema changes, no code changes
(SCOPE FENCE: evidence ONLY). The probe ran from the b1 worktree
(`/tmp/wt_graph_leg_closeout`, branch `feature/graph-leg-closeout`, HEAD `8b91310ac` = the b1
commit) so `ALLOWED_EXPANSION_RELS` is the post-b1 7-name set.

## Method

One fixed code-symbol seed with known edges, discovered from the live graph (a real
`repository_id`/`acl_scope` pair whose symbols carry CALLS edges), was run through the exact
`_neighbors`-shape query the expansion builds (`MATCH (n)-[r:<union>]-(m) ...` with the
traversal ACL clause), capturing the neo4j server notifications on `ResultSummary`. The union
strings are the ONLY variable:

| Probe | Union | What it shows |
|---|---|---|
| A — PRE-B1 repro | the pre-prune 10-rel union (`DEFINES\|IMPORTS\|CALLS\|TESTED_BY\|PRODUCED_BY\|PRECEDES\|SUPERSEDES\|CONTRADICTS\|CONTAINS\|AFFECTS`, from the pre-b1 tree / p0 pin) | the baseline warning set |
| B — POST-B1 | the current allowlist union — `CALLS\|CONTAINS\|DEFINES\|IMPORTS\|PRODUCED_BY\|SUPERSEDES\|TESTED_BY` (7 rels, `ALLOWED_EXPANSION_RELS` at `8b91310ac`) | the real post-prune expansion query |
| C — post-c2 (ILLUSTRATIVE) | `B` minus `PRODUCED_BY` (6 rels) | the state once c2's writer creates PRODUCED_BY edges (its rel-type token then exists) |

Seed: `SymbolVersion` `568365d6ce31fa404d0a6839c4478a263b300eca6e5aeec2c360f94b20ab2506` in
`repository_id = acl_scope = self-cap2a_p2_bespoke` (a campaign cell repo with real
CALLS/TESTED_BY/DEFINES edges), traversed under that repo's own scoped ACL.

## Results

### Probe A — PRE-B1 (10-rel union): 3 server warnings

```
Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning:
  "the missing relationship type is: PRODUCED_BY"
Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning:
  "the missing relationship type is: PRECEDES"
Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning:
  "the missing relationship type is: CONTRADICTS"
```

Exactly the p0 pin's capture — CONTRADICTS/PRECEDES/PRODUCED_BY have no rel-type token in the
store (nothing ever creates them; AFFECTS did not warn even pre-prune because its token exists
from the dormant writer path). This is the fresh-repro baseline on the same input.

### Probe B — POST-B1 (current 7-rel allowlist): 1 server warning

```
Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning:
  "the missing relationship type is: PRODUCED_BY"
```

The prune removed CONTRADICTS and PRECEDES from the emitted rel pattern — those two warnings
are gone. **PRODUCED_BY still warns because it is deliberately STILL allowlisted** (the c1
design `docs/designs/current/graph_leg_associative_edges.md` claims it for the first
associative family; `b1_prune_expansion_rels` keeps claimed names by rule) and its rel-type
token does not exist until the c2 writer creates the first edges. This is the designed
interim state, not a prune leak — b2 runs before c2 in the wave order.

**graph_paths is NON-EMPTY for the seed (the expansion works):** `expand_candidates` on the
seed returned **22 nodes** at `max_depth=2` — rel-type mix `TESTED_BY 13 | SUPERSEDES 3 |
DEFINES 3 | CONTAINS 2`, depth `{0: 1, 1: 7, 2: 14}` — so the real expansion path traverses the
allowlisted edges normally.

### Probe C — POST-C2 (illustrative, 6-rel union without PRODUCED_BY): 0 warnings

```
(no server notifications)
```

Removing PRODUCED_BY from the union yields a fully clean query — demonstrating the exact
end-state the wave's `c2_assoc_edge_writer` produces (once PRODUCED_BY edges exist, the token
exists and even the retained name stops warning). Labeled ILLUSTRATIVE: the code keeps
PRODUCED_BY allowlisted per the c1 claim.

### IMPACT union (`IMPACT_EXPANSION_RELS`, 6 rels) — 1 warning

`IMPACT_EXPANSION_RELS = ALLOWED − {SUPERSEDES}` still carries PRODUCED_BY (it is not a
version-history edge), so the impact-traversal union (`evidence_analyzer`) shows the same
single residual warning as Probe B — also resolved by c2.

## Verdict

| Claim (b2 DONE_WHEN) | Result |
|---|---|
| Expansion query no longer emits the UNUSED-rel warnings (the prune target) | **PASS** — warnings dropped **3 → 1**; CONTRADICTS and PRECEDES (no writer, unclaimed) no longer appear in the emitted rel pattern and their `UnknownRelationshipTypeWarning`s are gone from the live server |
| Residual PRODUCED_BY warning accounted for | **PASS** — the sole remaining warning is the c1-claimed name, retained by design pending its c2 writer; Probe C shows 0 warnings in the post-c2 state |
| graph_paths non-empty for a symbol with known edges | **PASS** — 22 nodes traversed (TESTED_BY/DEFINES/CONTAINS/SUPERSEDES) from seed `568365d6…` |

**b2 verdict: PASS.** The post-prune expansion is clean of every rel the prune targeted; the
single remaining warning is PRODUCED_BY, which is c1-claimed (kept on purpose) and disappears
once `c2_assoc_edge_writer` lands (Probe C proves the 0-warning end state on the same input).
Scope fence honored: evidence only — no schema or code changed by this phase.
