---
status: accepted
---

# flash-exploration — scope 1: self-derived skill + C4 arm

**Loop under test:** the ladder's own passing designs → one procedural skill → ingest → retrieve →
use in a new generation arm. This is the machine's first full "explore → derive → reuse →
measure" turn.

**Skill (live).** Derived by contemplation over the 12 round-1 exports: a single `TaskManager`
with the contract methods, tasks in an id-keyed mapping, explicit `depends_on` id lists,
validation in private helpers, cycle detection before mutation. Support 12/12, uncertainty 0.35,
evidence = the 12 cell records, validity window = the evidence digest.
`knowledge_id=3c4d382ea67744ba4413237f2ca76f019437fece50655e62d3678d14497579e0`
(`workload:skill/flash-ladder/taskman#pattern`), minted through the verified pattern projection
path (`scripts/kb_produce_skill.py`; addendum §13).

## Primary endpoint — MET

All three C4 cells selected the skill into the augmented prompt: each agent phase's
`selected_evidence_ids` (16 records) contains the skill id, with `fallback_mode=lexical_graph_only`
and the deterministic constructor; all three passed the pristine contract 13/13.
**Derivation → ingestion → retrieval → use works end-to-end.**

## Secondary endpoint — FLAT

| Cond | Q | D | ΔD vs C0 |
|---|---|---|---|
| C0 | 3/3 | 0.3571 | — |
| C3 (findings only) | 3/3 | 0.4194 | +0.0623 |
| **C4 (skill + findings)** | 3/3 | **0.3607** | **+0.0036** |

Quality stays saturated; diversity is flat within the registered margin (n=3, CIs wide,
descriptive only). On this task the skill changes prompt content but not measured behaviour.

## Validity catch (disclosed)

The first C4 scoring reported D=0.017 ("convergence collapse"). That was an artifact: the
executor's export glob had captured the **committed ladder evidence** under
`experiments/ladder_evidence/.../taskman/` into each C4 cell, and the collector scored those
pre-existing packages instead of the cells' own designs. Fixed: exports are now the
`base..sha` diff intersected with taskman sources; the collector accepts the record's
`changed_files` and never scans `experiments/`. Re-scored after re-export; the frozen round-1
numbers reproduce **exactly** under the fixed scorer (verified). C4 evidence frozen at
`experiments/ladder_evidence/c4/`.

## Reading

- The mechanical loop is proven; the behavioural null is honest and expected on a task whose
  quality saturated in round 1.
- A confirmatory n=8 C0-vs-C4 grid would be the registered way to look for movement, but a
  saturated task is unlikely to discriminate; a harder task family (or a task whose baseline
  quality is mixed) is the better next measurement.
- Next: scope 2 — the research & synthesis layer, first applied to the Control Room facelift.
