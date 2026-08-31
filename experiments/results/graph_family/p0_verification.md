# persistent_code_graph — p0 verification record (spec SHA pinned + the design §2/§5 mandate's pins verified)

**Phase:** `p0_pin_mandate` (spec `persistent_code_graph@0.1`).
**Role:** verification — the design §2/§5 mandate (`docs/designs/proposed/neo4j_graph_analysis_design.md`
§2 "Part A — the persistent code graph" + §5 "The sequencing"). Append this spec's SHA256 to the
design's header (the ONLY edit allowed). Verify the pins: the wall-is-the-fixture rule, the
semantics (behavioral vs structural) declared, the graph-additive-with-rollback rule, the
pre-verification-as-a-query rule. A deviation is a FAILED finding.
**Date:** 2026-08-31.
**Source revision (branch HEAD at phase start):** `a59a68951`.

## Pinned header

`docs/designs/proposed/neo4j_graph_analysis_design.md` header now carries the spec SHA256:

```
**Spec:** `persistent_code_graph` (`workflows/repository/persistent_code_graph.yaml` SHA256
`3b7984bc7ff6587d423592562056c48b6538c85bdffc06d2716d2d45886cebe7`; `persistent_code_graph@0.1`).
```

Measured: `sha256sum workflows/repository/persistent_code_graph.yaml` =
`3b7984bc7ff6587d423592562056c48b6538c85bdffc06d2716d2d45886cebe7` — **MATCHES**. The header was
appended as the ONLY edit (verified via `git diff`: exactly one inserted `**Spec:**` line +
blank line; no other change to the design). No further edit is needed.

## Verification items

| # | item | pinned value | verification | finding |
|---|---|---|---|---|
| 1 | spec SHA pinned in the graph-analysis header | `3b7984bc…` | `sha256sum` of the actual spec file matches the header; the header append is the ONLY edit | **PASS** |
| 2 | the wall-is-the-fixture rule | "THE WALL IS THE FIXTURE: the 2e reproduction must reproduce the wall's facts — the structural edges EXIST in the persistent graph AND the impacted counter read 0; a reproduction that cannot show BOTH side-by-side is a FAILED finding" | present in the spec `hard_rules` (2); the design §5 item 2 ("the 2e construction becomes the verification fixture — the graph query reproduces the 2e wall's facts") + §6 ("the 2e lesson is recorded as the motivating fixture") | **PASS** |
| 3 | the semantics (behavioral vs structural) declared | "THE SEMANTICS PINNED: the impacted definition (behavioral vs structural — the 2e lesson) is a DECLARED choice in the seam, queryable + auditable; an implicit definition is a FAILED finding" | present in the spec `hard_rules` (3); the design §2 ("the design pins the impacted definition (behavioral vs structural, the 2e lesson) as a declared choice, queryable, auditable") | **PASS** |
| 4 | the graph-additive-with-rollback rule | "GRAPH-ADDITIVE WITH ROLLBACK: the seam falls back to the in-process AST walk on ANY graph failure (down / empty / timeout) — the graph never gates a run; a seam that blocks on the graph is a FAILED finding" | present in the spec `hard_rules` (4); the design §5 item 5 ("each with the tests + the rollback (the graph is additive; the seam falls back to the in-process walk on any graph failure)") | **PASS** |
| 5 | the pre-verification-as-a-query rule | "THE PRE-VERIFICATION IS A QUERY: 'does the construction's changed symbol have structural dependants?' asked against the persistent graph BEFORE any grid — the answer visible + recorded" | present in the spec `hard_rules` (5); the design §2 ("the p1 pre-verification (the 2e lesson) becomes a graph query … asked BEFORE the grid runs, with the answer visible") | **PASS** |

## Findings

1. **All four pins verify — no deviation.** Each mandate pin is present in the design §2/§5 and
   consistent with the spec's `hard_rules`: the wall-is-the-fixture rule (spec hard rule 2 ≡
   design §5.2 + §6), the semantics-declared rule (spec hard rule 3 ≡ design §2), the
   additive-with-rollback rule (spec hard rule 4 ≡ design §5.5), the pre-verification-as-a-query
   rule (spec hard rule 5 ≡ design §2). No pin is contradicted anywhere in the spec's phases —
   p1 builds the graph, p2 reproduces the wall (the fixture), p3 runs the pre-verification query,
   p4 wires the seam with the declared semantics + the rollback posture.
2. **The semantics wording is consistent across the two documents.** The spec hard rule 3 pins
   "behavioral vs structural" as a "DECLARED choice in the seam, queryable + auditable"; the
   design §2 pins the same definition as "a declared choice, queryable, auditable". The design's
   §1 names the lesson that grounds it (the impact counter computes a BEHAVIORAL impact; the
   constructions assumed STRUCTURAL reach). No divergence.
3. **The rollback is the default posture, additive-only.** Spec hard rule 4 ("the graph never
   gates a run") and the design §5 item 5 ("the graph is additive; the seam falls back to the
   in-process walk on any graph failure") agree, and the spec's question repeats it ("additive,
   never a gate"). Consistent.

**LOG:** pinned header verified (SHA matches; the ONLY allowed edit made once, on this phase) +
5 of 5 verification items PASS, 0 FAILED findings. **PASS.**
