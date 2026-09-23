---
status: accepted
---

# Hindsight dossier (vendored) — for the `hindsight_adoption` workflow

**What this is.** The external material a cell can actually read. Cells run with **no external
egress** (the fleet allows only model endpoints), so the `hindsight_adoption` workflow cannot fetch
`hindsight.vectorize.io` or clone GitHub at run time. This directory carries the dossier instead.

**Provenance.** Source: [`vectorize-io/hindsight`](https://github.com/vectorize-io/hindsight),
**MIT-licensed**, shallow clone at commit `a7eafb2f395b3c905e9e577da691414d3ca8d08c` (2026-09-23);
docs pages at `hindsight.vectorize.io` v0.10. Excerpts below are quoted from that clone and are
attributed by path. The comparative read lives in
[`../hindsight_memory_solution_dissection.md`](../hindsight_memory_solution_dissection.md) (the
dissection: nouns mapped, convergences, divergences, borrow candidates).

**Reading order for the dive.**

1. `../hindsight_memory_solution_dissection.md` — the whole-solution read (§1–§9) + the source-level
   addendum (§10–§11).
2. `source_notes.md` (this directory) — the load-bearing excerpts, by subsystem, with clone paths.
3. The repo's own surfaces, per the workflow's domain context (the adoption targets).

**How adopted items get gated (the repo's rules, summarized for the dive).**

- **Generated surfaces** (`AGENTS.md`, `CLAUDE.md`, the four `.opencode/` trees + `.claude/`
  mirrors) are owned by `scripts/_gen_instructions.py`; edit the `agent_config/` source, then
  regenerate; `python3 scripts/_gen_instructions.py --check` must stay green.
- **Hand-authored, outside the generator** (edit directly): `.opencode/tools/`,
  `.opencode/plugins/`, `opencode.json`.
- **Every docs file needs YAML front-matter** with a valid `status`; `docs/reviews/*` must be
  `status: accepted`, `docs/designs/proposed/*` must be `status: proposed`
  (`tests/test_doc_lifecycle.py` is the gate — it caught a missing status on this very directory's
  sibling doc, hotfixed in PR #161).
- **Epistemics**: measured-or-absent; named states, never a fabricated zero; authority ordering
  `POLICY > SOURCE > MEASURED > DERIVED > ADVISORY`; `[M]/[C]/[H]/[X]/[P]` tags on claims.
- **Doctrine**: when the documented path fails, record the gap — do not build around it; a net-new
  top-level mechanism needs a one-line justification naming the gap it closes.
- **No weakened discipline**: adopting a belief/consolidation idea must never replace a measured
  value or a gate; keep the economics plane (admission/leases/settlement) and the permanence gate
  intact.
