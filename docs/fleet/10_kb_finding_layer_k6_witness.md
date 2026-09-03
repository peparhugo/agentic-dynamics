---
status: accepted
---

# kb_finding_layer k6 — THE WITNESS: the finding layer is real

**Status: PASS · Role: `kb_finding_layer` k6 (`k6_witness`).** The wave's verdict phase: run ONE
minimal real phase under DEFAULT settings, prove its finding lands in the KB, and prove the
2026-09-02 retrieval probe's "flat, not rich" verdict has INVERTED — the original
`control_db_evidence` query now returns the k2-backfilled finding in the top results. Every
number below is a live command against the machine-local KB state (Neo4j `bolt://localhost:7687`,
Redis 6380 db 2, Chroma `knowledge_chunks_v1`) executed from the wave checkout's `src`.

The witness ran and PASSED — but only after the witness itself exposed TWO gaps that had kept
the finding layer invisible, and this phase fixed both (the SHAPE's mandate: *"If the witness
exposes a gap (the emit didn't land, the order didn't fix), FIX IT IN THIS PHASE."*).

---

## 1. The witness exposed gap (a) — the default-on emit NEVER fired for this orchestration's phases

**Root cause (code + history).** The k1 default-on gate is
`if _finding_emit_enabled(rag_params, phase_def) and pr.commit_hash:` (`workflow_runner.py`,
commit block), where `pr.commit_hash = _git_commit(wd, name, goal)`. `_git_commit` stages + commits
the phase's *uncommitted* work and returns its short sha — **or returns `""` when the tree is
clean** ("nothing to commit"). Every phase of this wave (k0–k5) was an AGENT that committed its
own work; at phase end the runner's `_git_commit` found a clean tree, returned `""`,
`pr.commit_hash` stayed `""`, and the emit gate was **false**. Consequence, measured across both
checkouts: ZERO phase findings from k1–k5 exist anywhere (0 artifacts, 0 registry rows, 0 graph
nodes mentioning `kb_finding_layer` or `self-wt_wave4`) — the k1 "default ON" was real in code
but unreachable for exactly the self-committed phases this runner produces. The k2–k5 phases
committed rich work and silently never emitted.

**Fix (this phase).** The commit block now adopts the phase's own HEAD when the tree is clean AND
the HEAD advanced past the pre-phase baseline (the commit-prefix gate has already certified every
commit in the window):

```python
if not pr.commit_hash:
    phase_head = _git_head(wd)
    if phase_head and phase_head != phase_head_before:
        pr.commit_hash = phase_head
```

A self-committed phase's finding now emits like any other's. Unit test
`test_finding_emit_fires_when_agent_self_commits` (tests/test_workflow_runner.py) proves an agent
that commits its own conforming work still emits, with `pr.commit_hash` = the agent's commit.

## 2. The witness exposed gap (b) — a durable finding is not a RETRIEVABLE finding

**Root cause (measured).** The k2 backfill produced 164 wave finding records as durable artifacts
(`experiments/results/kb/<id>.json`) + emit-time registry rows — but the retrieval LEGS never saw
them. Measured at the start of this phase:

- `kb-chroma-v1` has NEVER consumed the change stream (`last-delivered 0-0`) → the dense leg
  still held only the 812 legacy docs from the pre-`637fd8455` projection.
- the `kb-neo4j-v1` / `kb-registry-v1` consumers run in containers whose `/repo` corpus overlay
  is `…/experiments/results` mounted from `/tmp/wt_fleet_submit` (a STALE fleet checkout), NOT the
  producer checkouts → a pointer event whose artifact lives at the main/wave checkout cannot be
  verified (`process_entry` reads the artifact and verifies `content_hash`) and is dead-lettered
  (dead-letter stream ≈ 7,996 entries; the registry group holds 2,461 pending across 60+ zombie
  consumers).

Consequence, measured via the wave `src` probe immediately before projection: the ORIGINAL
2026-09-02 query returned **61 selected, source mix `{'code': 21, 'review': 40}`, top-10 ALL code,
ZERO finding candidates** — the k2 findings existed but were invisible to retrieval. The
"distilled layer answers findings questions with findings" claim was unwritable.

**Fix (this phase).** `scripts/kb_project_findings.py` (registered: `agentic-dynamics knowledge
project-findings`) deterministically materializes the durable finding layer into the retrieval
legs using the SAME handler bodies the stream consumers run (`kb_worker.build_handler`): Chroma
`knowledge_chunks_v1` upsert, Neo4j `Knowledge` MERGE, append-only registry row. NO LLM; keyed by
`knowledge_id` so a re-run is a no-op. This is the emit-side "no live-consumer dependency"
materialization pattern (`kb_produce_campaign_evidence` already materializes its registry row at
emit time) extended to the legs the live consumers cannot reach. Projection result:

```
projected legs={'chroma': 165, 'neo4j': 165, 'registry': 1} records=165
neo4j wave-backfill finding nodes: 164 · neo4j nodes mentioning control_db_evidence: 1
neo4j witness-scope nodes: 1 · chroma count: 812 -> 977
```

## 3. THE WITNESS RUN — one minimal real phase, DEFAULT settings

Synthetic one-phase spec (`/tmp/kb_finding_layer_witness.yaml`, full content in §7), run via
`scripts/run_workflow.py` with the wave code, in a fresh worktree, model `deepseek/deepseek-v4-flash`,
**no emit_self opt-in, no rag params, no env disarm** (the k1 default carried it):

| Field | Value |
|---|---|
| Control run | `run-8e4b45836b21` (the nested witness run) |
| Phase | `witness_phase` (kind agent) — wrote `witness_finding.txt`, one conclusion sentence |
| Phase status | `ok`, cost **$0.0040**, tokens 26,206 |
| Phase commit | `7b1941ff1` (`[workflow] witness_phase — …`) — the runner's clean-tree adoption fired |
| **Emitted finding** | `030f9574763ced0f30e35d7c8d8cb5aeb5d511dc563b6a1015ff60f09d5912f8` |
| Durable artifact | `experiments/results/kb/030f9574….json` (committed with this phase) |
| Registry row | appended (committed with this phase) |
| Scope | `repository_id = acl_scope = self-wt_wave4_witness` (the cell, never global) |

The finding text carries the k1-enriched fields — status, tests verdict (None → ADVISORY, never a
fabricated MEASURED), cost, commit, and the phase's own conclusion line:

```
kb_finding_layer k6 witness: a real phas phase witness_phase -> test_executed_success None,
cost $0.0040, tokens 26206; status ok, commit 7b1941ff1, conclusion kb_finding_layer k6 witness
phase finding: default settings emitted this committed phase's scoped finding into the KB
retrieval legs
```

## 4. The probe evidence — before / after

**Before (2026-09-02 verdict, k0 pin):** 61 selected, source mix `{'code': 21, '': 40}`, top-6 all
code, `graph_paths {}`. **Immediately pre-witness this phase (wave src, findings unprojected):**
61 selected, `{'code': 21, 'review': 40}`, top-10 all code, ZERO finding candidates.

**After** (finding layer projected; identical probe shapes, `repository_id=""`, `acl_scope=""`,
phase objective set):

| Probe | Query | After — selected | After — top-K | The assertion |
|---|---|---|---|---|
| WITNESS shape | "kb_finding_layer witness phase finding emission default settings knowledge base" + objective "determine what the kb_finding_layer wave's k6 witness phase concluded" | 57, mix `{'finding': 40, 'code': 17}` | top-5 all `finding` | **witness finding at rank 2** — in the top results |
| ORIGINAL 2026-09-02 | "control database per-phase evidence recording findings" + objective "determine what the control_db_evidence wave concluded" | 60, mix `{'finding': 41, 'code': 19}` | top-5 all `finding` | **`control_db_evidence` backfilled finding `6961dcfb…` at rank 4** — the 'flat, not rich' verdict INVERTED |

Top-5 for the ORIGINAL probe after: `c3ceb98d…` (finding, wave:control_room_ui_implement),
`751827d7…` (finding), `26f60dc2…` (finding, wave:control_db_followups),
**`6961dcfb…` (finding, wave:control_db_evidence — the k2 backfill)**, `40416996…` (finding).
Zero code signatures above any of them.

## 5. VERIFY (the witness's evidence IS the verification)

- (a) **The emit landed**: durable artifact present at `experiments/results/kb/030f9574…json`
  (committed); registry row present; record projected into BOTH retrieval legs (chroma count
  812→977, neo4j witness-scope node present); retrievable by the probe shape.
- (b) **The original probe now returns rich results**: the k2-backfilled `control_db_evidence`
  finding returns at rank 4 of 60, in a top-5 that is entirely findings — the 'flat, not rich'
  verdict is inverted, measured with the identical query + phase objective the 2026-09-02 probe
  used.
- (c) **The k1 default carried the witness**: no opt-in flag anywhere in the run; the emit fired
  through `_finding_emit_enabled`'s default path plus the new clean-tree adoption.

## 6. Scope compliance

- **Fixed:** `workflow_runner.py` (clean-tree commit adoption — the emission gap); new
  `scripts/kb_project_findings.py` (the leg-projection gap) + CLI + CONTEXT manifest + tests
  (`test_finding_emit_fires_when_agent_self_commits`, `tests/test_kb_project_findings.py`).
- **Ran:** the synthetic witness phase (spec content in §7) with DEFAULT settings; projected the
  finding layer (164 backfill + 1 witness) into chroma/neo4j/registry.
- **Committed:** the witness finding artifact, the witness run ledger
  (`experiments/results/workflows/kb_finding_layer_witness/20260903T181250Z.json`), and the
  witness registry row.
- **Not done, deliberately:** the fleet container corpus-overlay mount
  (`/tmp/wt_fleet_submit` shadowing `/repo/experiments/results`) is out of scope — the projection
  script is the deterministic no-live-consumer remedy, documented here as the reason. Spec-index
  STATUS.md/index.json drift (185 vs 188) is pre-existing and out of scope (k4 noted it).

## 7. The synthetic witness spec (reproducible bytes)

Full content of `/tmp/kb_finding_layer_witness.yaml` executed for this witness (kept OUT of
`workflows/**` so the derived spec lifecycle index is untouched):

```yaml
name: kb_finding_layer_witness
question: >- THE WITNESS (kb_finding_layer k6): a minimal real agent phase run with DEFAULT
  settings to prove the k1 default-on finding emission lands in the KB and the 2026-09-02
  retrieval probe's "flat, not rich" verdict has inverted.
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects: {repository: true, external_services: false}
repeatable: false
workflow:
  kind: agent_task
  params:
    language: python
    fork: false
    context: {domain_context: "the k6 witness phase of kb_finding_layer", challenge_context: "prove the emit fires"}
    phases:
      - name: witness_phase
        kind: agent
        scope: implementation
        timeout: 1500
        prompt: |
          GOAL: {goal}
          ROLE: the k6 witness phase of the kb_finding_layer wave. Do the following only:
          1. Write ONE file at the worktree root named `witness_finding.txt` containing a
             single sentence beginning with the exact phrase: "kb_finding_layer k6 witness
             phase finding: default settings emitted this committed phase's scoped finding
             into the KB retrieval legs".
          2. Leave the change for the runner to commit (do NOT commit yourself).
          3. Your FINAL message must be exactly one line — that conclusion sentence, verbatim.
factors: [{name: model, levels: [deepseek/deepseek-v4-flash]}]
design: factorial
rules: []
metrics: []
writeup: {format: lab_book, sections: [question]}
stop: {budget_usd: 0.10, max_attempts: 1}
```

## 8. Verdict

| Mandate (hard rule 6 / k6 SHAPE) | Evidence | Result |
|---|---|---|
| run ONE minimal real phase with DEFAULT settings | `run-8e4b45836b21`, phase `witness_phase` ok, $0.004, commit `7b1941ff1` | **PASS** |
| the phase's finding lands in the KB | durable artifact `030f9574…` + registry row + chroma (977) + neo4j (witness node) | **PASS** |
| witness finding in the top results of the probe shape | rank 2 of 57 (top-5 all findings) | **PASS** |
| the ORIGINAL 2026-09-02 probe returns the control_db_evidence finding in the top results | `6961dcfb…` at rank 4 of 60 (top-5 all findings); was 0 findings / top-code | **PASS** — 'flat, not rich' INVERTED |
| any gap exposed is fixed in this phase | (a) clean-tree emission adoption; (b) `kb_project_findings.py` leg projection | **PASS** |

**k6 verdict: PASS.** The finding layer is real and retrievable. The witness exposed two genuine
gaps — the default-on emit never fired for self-committed phases, and a durable finding was not a
retrievable finding — and both are fixed with tests + committed evidence. `k7_adversarial` may
proceed and should re-run both probes itself against the machine-local KB.
