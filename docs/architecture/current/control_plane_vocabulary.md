---
status: accepted
---
# Control-plane vocabulary: eight things that were all called "the index"

_Landed by `control_db_publication` p3 (the projection-watermark phase)._

## Why this document exists

The deep review's central diagnosis was that the control plane's state is **multi-carrier**:
"the workflow is complete" could mean the agent said so, the ledger says `ok`, the YAML says
`completed`, git contains the commits, Redis says done, the registry consumed the result, or
the site deployed. The control database (p1), the outbox (p2), and the projection watermarks
(p3) each remove one carrier's ambiguity.

But the carriers were also **named** ambiguously, and that is a separate defect with the same
consequence. At least eight distinct artifacts in this repo were each referred to, in some
docstring or comment, as *"the index"*. `scripts/kb_worker.py` alone used the word for three
different things within two hundred lines: the append-only registry log it writes, the
"index layers" of the canonical-state design, and an in-process Python dict of flags. A reader
who resolves "the index" to the wrong referent draws a confident, wrong conclusion — and
because every one of these artifacts is *some* kind of catalog of *some* kind of record, the
wrong referent is always plausible enough to survive review.

This is the naming half of the same problem the control database solves structurally: **one
name, one thing.** The table below is the vocabulary. When a doc or a comment means one of
these, it uses that name.

## The eight names

| Name | What it actually is | Where it lives | Who writes it |
|---|---|---|---|
| **spec_catalog** | The derived lifecycle index of every experiment/workflow spec: what exists, what is done, when, and the supersedes chains. | `experiments/specs/index.json` (machine) + `experiments/specs/STATUS.md` (human) | `scripts/spec_status.py` — derived, never hand-edited |
| **run_state** | The orchestrator-owned durable state machine: runs, step attempts, gate results, approvals, promotions, the outbox, and the projection watermarks. The control plane's single source of truth. | `experiments/results/control/control.db` (SQLite) | the orchestrator (`scripts/run_workflow.py`'s composition root) — single writer, except the watermark rows (below) |
| **knowledge_event_stream** | The durable Redis Stream of pointer events (no bodies) that carries every knowledge change to its four consumer groups. | `kb:v1:changes` on Redis 6380 / DB 2 | producers via `knowledge_stream.publish_event`, delivered by `control.outbox` |
| **knowledge_registry_log** | The flat, append-only log of one JSON line per projected record — never rewritten in place. | `experiments/results/registry_index.jsonl` | the `kb-registry-v1` consumer group (`scripts/kb_worker.py`) |
| **knowledge_manifest** | The *compacted* view of the registry log: latest-per-entity, with `lifecycle_state` (`current`/`superseded`/`tombstoned`) resolved from the supersede/delete chain. | the `registry` array in `data_manifest.json` | `scripts/generate_manifest.py` |
| **chroma_projection** | The dense-vector projection of knowledge records, used for semantic retrieval. | the `knowledge_chunks_v1` Chroma collection | the `kb-chroma-v1` consumer group |
| **neo4j_projection** | The graph projection of knowledge records and their lineage edges, used for lexical/full-text retrieval and traversal. | the Neo4j graph | the `kb-neo4j-v1` consumer group |
| **publication_receipt** | The single record of what a publication actually published: the candidate sha, the verified projections, the built data, and both Firebase deployment outcomes. | (p6's deliverable) | `agentic-dynamics publish release` |

Two further index-like things exist and are deliberately **not** in the table above, because
they are process-local rather than durable state. They are named here so that a reader who
meets them knows they are not one of the eight:

- the **source-type lookup** (`kb:v1:source_type_index`) — a lightweight Redis hash used only
  by the actuation lineage gate, a stand-in for the knowledge_registry_log until that surface
  landed. It is a gate's scratch space, not a catalog.
- the **in-process flag map** — a plain Python dict inside one `kb_worker.py` process, used by
  the flag auto-clear rule to correlate an observation back to a flag it saw earlier in the
  same run. It does not survive the process.

## The relationships that matter

```
                 producers (facts, specs, stories, reviews, ledgers, observations)
                                          │
                                    control.outbox          ← the ONE emission path (p2)
                                          │
                              knowledge_event_stream         ← kb:v1:changes
                                          │
              ┌──────────────┬────────────┴─────────────┬──────────────┐
    kb-registry-v1     kb-chroma-v1              kb-neo4j-v1     kb-ledger-v1
              │              │                         │              │
   knowledge_registry_log  chroma_projection    neo4j_projection   (checkpoint hash)
              │
      knowledge_manifest    ← the compacted, latest-per-entity view
```

Every one of those four consumer groups reports a **projection watermark** into `run_state`'s
`projection_watermarks` table: how far it has confirmed, how far behind the stream head it is,
when it last reported, and its last error. That table is what makes the fan-out above
observable rather than merely hoped-for — see `src/agentic_dynamics/control/projection_watermarks.py`.

The `spec_catalog` sits outside this chain entirely. It indexes *specs* (what work exists);
`run_state` records *runs* (what happened). Conflating the two is the single most common
instance of the ambiguity this document removes, because "the workflow is complete" is a
sentence you can read off either one — and they can disagree.

## The one documented exception to single-writer

`run_state` is orchestrator-owned: one writer, by design (p1). `projection_watermarks` is the
exception — **each projector owns its own watermark row**. Nobody else can know when
`kb-chroma-v1` confirmed an event, and routing that fact through the orchestrator would
reintroduce the indirection the table removes. The exception is safe because the table is
partitioned by `projection` (one row per projector, no shared rows) and because SQLite's WAL
mode serialises the writes behind `busy_timeout`.

## Using these names

- In a **docstring or comment**, prefer the vocabulary name over "the index" whenever more than
  one of these artifacts is plausibly in scope. Where only one is in scope and the file's own
  subject makes it unambiguous, a bare "the index" is tolerable — but the vocabulary name is
  never wrong.
- In **code**, the existing identifiers stay as they are (`REGISTRY_INDEX_PATH`,
  `index.json`, …). Renaming symbols would be a refactor with a real migration cost and no
  correctness gain; the ambiguity that actually misleads readers lives in prose, and that is
  where p3's relabel pass applies.
- When a **new** durable catalog is added, give it a name here first. An artifact that arrives
  without a distinct name gets called "the index" by the next person to describe it, which is
  how this list reached eight.
