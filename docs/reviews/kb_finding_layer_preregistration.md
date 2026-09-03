---
status: accepted
kind: preregistration
spec: kb_finding_layer
phase: k0_pin_spec
run: run-77f7b899f4f8
generated_at: 2026-09-03T13:39:33Z
---

# Preregistration — `kb_finding_layer` (k0_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
wave executes (`k1_emit_default_on`, `k2_backfill`, `k3_retrieval_order`, `k4_graph_and_untyped`,
`k5_narrator`, `k6_witness`, `k7_adversarial`, `k8_test_gate`). Its purpose is twofold, and both
halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the premises, do not assert them.** The five edges this wave builds on are stated as
   current-state claims in the spec's `current_state` block (authored 2026-09-02): emit_self
   default OFF, a one-liner finding text, empty-shell finding records with the wave conclusions
   absent, retrieval returning code/empty-type records for a findings query, and graph_paths 0.
   This phase re-derives each edge against the actual code AND the live KB at the MAIN checkout
   (the machine-local state, per the mandate) and records the command that produced the evidence,
   so a reader can reproduce every finding without trusting this document. **An edge that does not
   hold is a FAILED finding.** If a claim could not be reproduced after THREE attempts, the
   deviation was to be recorded and the claim FAILED — never looped.

No claim below was accepted on the spec's authority. Every edge was verified with a live probe at
`2026-09-03T13:08–13:39Z`, against the code at the worktree HEAD and the machine-local KB state at
the main checkout. All five edges **PASS** — each reproduced the spec's current-state claim with
measured evidence. The evidence is quoted so the adversarial phase (k7) can re-run every probe.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/kb_finding_layer.yaml` |
| Spec **SHA256** | `ea21ccecbd0a4f696100ae982dc184c7bc35c1227894e7ec6a10b53a8d67b62d` |
| Spec size | 24,305 bytes |
| Worktree HEAD (git sha) | `64d1ded099e5f3ed3a25f1d356fa8783265c6446` (`[workflow] spec: kb_finding_layer …`) |
| Branch | detached HEAD — worktree `/tmp/wt_wave4` executes this run |
| Main checkout HEAD | `aeb1850d4d018a65103ede1fd862ad9a595936e3` (`self-knowledge layer: actor layering …`) — the machine-local state host |
| src/ parity | identical — `git diff 64d1ded09…HEAD -- src/ scripts/` is empty (verified; the wave's code anchors are the same bytes in the worktree and at main) |
| Run (this phase) | `run-77f7b899f4f8` — `kb_finding_layer`, `state: running`, started `2026-09-03T13:08:01Z`, model `deepseek/deepseek-v4-flash`, orchestrated by `run_workflow.py --spec /tmp/wt_wave4/workflows/repository/kb_finding_layer.yaml` |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local, main checkout), `schema_version: 4`, `control_epoch: 116` |
| KB machine-local state | main checkout `/home/drseuss/ai-finops-framework/experiments/results/registry_index.jsonl` + `kb/<id>.json` + Redis 6380 db 2 + Chroma `localhost:8000` + Neo4j `bolt://localhost:7687` |
| Goal prefix | `Close the knowledge-base finding-layer gap` |
| Pinned at | 2026-09-03T13:39:33Z |

Reproduce the pin — these are the EXACT bytes the run executes:

```bash
sha256sum workflows/repository/kb_finding_layer.yaml
# ea21ccecbd0a4f696100ae982dc184c7bc35c1227894e7ec6a10b53a8d67b62d
git rev-parse HEAD          # in the executing worktree /tmp/wt_wave4
# 64d1ded099e5f3ed3a25f1d356fa8783265c6446
```

If either value differs when k7 (adversarial) or k8 (test gate) runs, the spec was edited mid-run
and the mandate this document pins is no longer the mandate being executed.

**Spec shape at the pin** — nine phases, all `kind: agent` except the terminal `k8_test_gate`
(`kind: test`):

| # | Phase | kind | scope |
|---|---|---|---|
| 0 | `k0_pin_spec` | agent | `implementation` |
| 1 | `k1_emit_default_on` | agent | `implementation` |
| 2 | `k2_backfill` | agent | `implementation` |
| 3 | `k3_retrieval_order` | agent | `implementation` |
| 4 | `k4_graph_and_untyped` | agent | `implementation` |
| 5 | `k5_narrator` | agent | `implementation` |
| 6 | `k6_witness` | agent | `implementation` |
| 7 | `k7_adversarial` | agent | `adversarial_readonly` |
| 8 | `k8_test_gate` | test | `implementation` |

---

## 2. Verified current-state edges (re-derived against code + the live KB)

Each edge is stated as the spec's `current_state` / `question` claims it, then **independently
re-derived**. The verdict legend is stated up front so no status is misread:

- **PASS** — the mandate's claim describes the state measured at the pin. The gap the wave was
  built to close is OPEN, verified with code + live-KB evidence. In a first-run pin this is the
  expected, positive result: it confirms the wave is targeting real state, not asserted state.
- **FAILED** — the mandate's claim does not hold as stated. Recorded with the deviation and the
  true state, per the "an edge that does not hold is a FAILED finding" rule.

Every probe below ran read-only from the main checkout (the machine-local KB host).

### Edge 1 — `emit_self` defaults OFF (workflow_runner.py:3421 gates on `rag_params.get("emit_self")`)

*Claim.* Spec runs never emit a phase finding unless a run opts in via `rag_params.emit_self`;
`emit_self` is opt-in, default OFF.

*Method (the gate + the param default + the spec's own params).*

```bash
grep -n "emit_self" src/agentic_dynamics/runtime/workflow_runner.py
grep -n "rag_params: dict" src/agentic_dynamics/runtime/workflow_runner.py
python3 -c "import yaml; s=yaml.safe_load(open('workflows/repository/kb_finding_layer.yaml')); print(list(s['workflow']['params'].keys()))"
grep -n "rag_augment\|emit_self" scripts/run_workflow.py
```

*Evidence.*

```
workflow_runner.py:3421:  if rag_params.get("emit_self") and pr.commit_hash:
workflow_runner.py:3422:      _emit_self_finding(pr, goal=goal, scope=cell_scope(wd))
workflow_runner.py:2736:  rag_params: dict[str, Any] | None = None,      # run_workflow signature default
workflow_runner.py:2920:  rag_augment = rag_augment if rag_augment is not None else bool(
workflow_runner.py:2921:      spec.workflow.params.get("rag_augment", False))
workflow_runner.py:2923:  rag_params = dict(rag_params or spec.workflow.params.get("rag", {}) or {})
params keys: ['language', 'fork', 'context', 'phases']      # kb_finding_layer carries NO rag block
run_workflow.py: no rag_augment / emit_self / rag_params arguments in main()'s run_workflow(...) call
```

The emit seam is the phase-boundary block at `workflow_runner.py:3417-3422`: *"Self-build
('progressive') producer — opt-in via `rag_params.emit_self`. … default OFF: only the 'self-built'
arm opts in"* — the gate is `if rag_params.get("emit_self") and pr.commit_hash:`. The `run_workflow`
parameter default is `rag_params: dict[str, Any] | None = None` (`:2736`), and the composition root
(`scripts/run_workflow.py`) passes **no** `rag_params`/`rag_augment` at the `run_workflow(...)` call
— so a spec run reaches `:2923` with `rag_params = {}` (this spec has no `rag:` block; its params
are `language/fork/context/phases`), `.get("emit_self")` is falsy, and the emit never fires.
`rag_augment` is likewise default-False unless a spec sets it (`:2920-2922`).

**PASS** — emit_self is default OFF for spec runs; only the retrieval_activation_augment_proof
family (the one spec family that sets `rag.params`) has ever enabled it. The default flip is the
k1 deliverable, and this edge is the open gap that justifies it.

### Edge 2 — the finding text is a one-liner (derive_phase_record)

*Claim.* `derive_phase_record` produces a one-line finding of the shape
`"<goal> phase <phase> -> test_executed_success <bool>, cost $<c>, tokens <n>"` — no status, no
commit sha, no conclusion, no tests_passed/total. (spec: *"the finding text is a one-liner … the
phase's conclusion when derivable"* is the k1 enrichment target.)

*Method.*

```bash
grep -n "def derive_phase_record" src/agentic_dynamics/knowledge/knowledge_ingestion.py
sed -n '450,510p' src/agentic_dynamics/knowledge/knowledge_ingestion.py
```

*Evidence* (the text assembly, `knowledge_ingestion.py:485-488`):

```python
text = (
    f"{goal[:40]} phase {phase} -> "
    f"test_executed_success {success}, cost ${cost:.4f}, tokens {tokens}"
)
```

The `text` is exactly one line: goal prefix (truncated to 40 chars) + phase name +
`test_executed_success <bool-or-None>` + cost + tokens. Authority is `MEASURED` when
`test_executed_success` is a real bool, `ADVISORY` when `None` (`:478-480`). The record carries NO
status field, NO commit sha as a finding field beyond the identity `revision`, NO
tests_passed/total, NO gate verdict, NO conclusion line — the fields k1 must add. Confirmed against
the code at the pin; the corpus samples in Edge 3 confirm the emitted records match this shape.

**PASS** — the finding text is the one-liner the spec claims.

### Edge 3 — the registry's finding records are empty shells + the wave conclusions are absent

*Claim.* The 64 registry `finding` records are near-empty shells; 0 hits for `control_db_evidence` /
`split-run` across them; the completed waves' conclusions (adversarial verdicts, the 17-spec shift,
the evidence-wave results) are absent from the KB entirely.

*Method (the live registry at the main checkout).*

```bash
cd /home/drseuss/ai-finops-framework   # the machine-local KB host
python3 - <<'EOF'
import json
from collections import Counter
c = Counter(); findings = []; total = 0
for line in open('experiments/results/registry_index.jsonl'):
    total += 1; d = json.loads(line)
    st = d.get('source_type') or '<MISSING>'; c[st] += 1
    if st == 'finding': findings.append(d)
print('total lines:', total)
print('source_type counts:', dict(c))
print('finding rows:', len(findings))
print('finding rows with text field:', sum(1 for d in findings if d.get('text')))
print('finding rows mentioning control_db_evidence:', sum(1 for d in findings if 'control_db_evidence' in json.dumps(d)))
print('finding rows mentioning split-run/split_run:', sum(1 for d in findings if 'split-run' in json.dumps(d) or 'split_run' in json.dumps(d)))
EOF
```

*Evidence.*

```
total lines: 41025
source_type counts: {'fact': 38713, 'spec': 326, '<MISSING>': 1194, 'story': 330,
                     'review': 242, 'finding': 64, 'meta_session': 27,
                     'context_snapshot': 11, 'report': 118}
finding rows: 64
finding rows with text field: 0
finding rows mentioning control_db_evidence: 0
finding rows mentioning split-run/split_run: 0
```

The 64 `finding` rows are metadata-only shells — registry lines carry no `text` field at all (text
lives in the per-record `experiments/results/kb/<knowledge_id>.json` artifacts), and the finding
rows point at bulk run-output files (`file://experiments/results/task_manager_*.json`,
`process_perturbation_resample_*.json`), all `observed_at 2026-08-19`, all `lifecycle_state:
current`. A full-file scan for the wave-conclusion keywords confirms their absence from the finding
layer:

```
rows mentioning control_db_evidence/split_run by source_type: {'fact': 133}
```

All 133 `control_db_evidence` / `split_run` mentions are **fact rows** (the CAP fact plane, in
`source_uri`/`logical_locator`), never `finding` rows. The 1,194 `<MISSING>`-source_type rows are
the supersede predecessor thin rows (registry writer emits them without `source_type` — the k4
audit target). Corroborating artifact census: the `kb/<id>.json` finding artifacts on disk (868)
are the OLD measured-finding/v1 experiment summaries (one-line `<model> under <condition> ->
correctness …, cost …, flail …` texts from `_results_summary.json`, `repository_id:
agentic-dynamics`), none mentioning the waves this wave must backfill. The completed waves'
conclusions (adversarial verdicts in `docs/reviews/*adversarial.md`, the 17-spec shift, the
evidence-wave results) are absent from the finding layer — they live only in `docs/reviews/`, which
is exactly the k2 backfill source.

**PASS** — finding records are empty shells and the wave conclusions are absent, with the counts
measured at the pin.

### Edge 4 — retrieval returns code/empty-type records for a findings query (the 2026-09-02 probe)

*Claim.* For a phase-objective findings query with `repository_id ""` (broad scope), retrieval
returns 21 code + 40 empty-source_type of 61 selected — flat code signatures, no distilled
findings.

*Method — the SAME probe the 2026-09-02 verdict used* (`repository_id=''`, `acl_scope=''`,
`phase_objective` set):

```bash
cd /home/drseuss/ai-finops-framework && timeout 120 python3 - <<'EOF'
import sys; sys.path.insert(0, 'src')
from agentic_dynamics.knowledge.augment import default_retrieve_fn
retrieve = default_retrieve_fn()
attempt = retrieve(
    "control database per-phase evidence recording findings",
    repository_id="", acl_scope="",
    phase_objective="determine what the control_db_evidence wave concluded",
)
sel = attempt.selected_evidence
print("selected:", len(sel))
st = {}
for c in sel:
    s = getattr(c, 'source_type', '?'); st[s] = st.get(s, 0) + 1
print("source mix:", st)
print("graph_paths:", attempt.graph_paths)
print("fallback_mode:", attempt.fallback_mode)
for i, c in enumerate(sel[:6]):
    print(f"  top{i+1}: source_type={getattr(c, 'source_type', '?')!r} text={getattr(c, 'text', '')[:70]!r}")
EOF
```

*Evidence.*

```
selected: 61
source mix: {'code': 21, '': 40}
graph_paths: {}
fallback_mode: full
  top1: source_type='code' text='_spawn_workers(phase: Phase)'
  top2: source_type='code' text='_workers_alive(phase: Phase)'
  top3: source_type='code' text='validate_workflow_routing(spec: ExperimentSpec, ...)'
  top4: source_type='code' text='build_constructor_prompt(...)'
  top5: source_type='code' text='render_evidence_packet(...)'
  top6: source_type='code' text='_execute_pr_merge(phase: PlanPhase, ...)'
```

The probe reproduces the spec's verdict **exactly**: 61 selected, source mix `{'code': 21, '': 40}`
(21 bare code signatures + 40 empty-source_type records), the top six all `source_type='code'`, and
a `control_db_evidence` findings question returns zero distilled findings. The 40 empty-source_type
records are the candidate-level form of the k4 untyped-record problem (retrieval `_source_type`
returns `""` when the store metadata carries no `source_type`; the registry's 1,194 missing-key
rows are the writer-side twin — both are k4's audit targets).

**PASS** — a findings query returns code/empty-type records, reproduced verbatim at the pin.

### Edge 5 — graph_paths 0 (run a probe + check the neo4j consumer state)

*Claim.* Both probes return `graph_paths 0`; the graph leg returns zero paths.

*Method (two probe shapes + the graph client + the consumer state).*

```bash
# shape A — the default-arguments probe (from the k0 Edge-4 heredoc, graph_paths printed {} above)
# shape B — a dedicated expansion probe with the retrieval's own seeds + generous timeout
python3 - <<'EOF'
from agentic_dynamics.knowledge.graph import Neo4jClient
g = Neo4jClient()
seeds = [c.id for c in attempt.selected_evidence[:6]]
out = g.expand_candidates(seeds, max_depth=2, max_neighbors=8, max_nodes=40,
                          timeout_ms=5000, repository_id="", acl_scope="")
print("expand_candidates:", len(out), "nodes")
print("depth distribution:", {d: sum(1 for n in out if n['depth']==d) for d in set(n['depth'] for n in out)})
# per-seed neighbor census under the empty-scope ACL
for seed in seeds:
    legacy = session.run("MATCH (n)-[r:DEFINES|IMPORTS|CALLS|TESTED_BY|PRODUCED_BY|PRECEDES|SUPERSEDES|CONTRADICTS|CONTAINS|AFFECTS]-(m) "
                         "WHERE n.knowledge_id = $seed AND NOT (m:ModuleVersion OR m:SymbolVersion) RETURN count(DISTINCT m)", seed=seed).single()[0]
# consumer state
python3 -c "import redis; r=redis.Redis(port=6380, db=2); [print(g) for g in r.xinfo_groups('kb:v1:changes')]"
```

*Evidence.*

```
probe A (default arguments):  graph_paths {} (selected 66)
probe B (scoped findings query): graph_paths {} (selected 61)     # the Edge-4 probe, same line
expand_candidates (real seeds, 5s): 6 nodes, depth distribution {0: 6}   # seeds resolve, ZERO hops
per-seed legacy-ACL neighbor census: 0,0,0,0,0,0  (the probe's top-6 code seeds have NO
  traversable neighbors under the empty-scope legacy-only ACL)
```

Consumer state (`XINFO GROUPS kb:v1:changes`, Redis 6380 db 2):

```
stream length 31,345
kb-neo4j-v1   consumers 3   pending 0   last-delivered 1788441108941-0   lag 0   entries-read 31,524
kb-registry-v1 consumers 61  pending 2,461  last-delivered 1788270321118-0  lag 657
kb-chroma-v1  consumers 0   pending 0   last-delivered 0-0            (never consumed)
kb-ledger-v1  consumers 0   pending 0   last-delivered 0-0            (never consumed)
```

The kb-neo4j-v1 consumer is **caught up** (lag 0, pending 0, actively reading). Yet both retrieval
probes return `graph_paths: {}` — empty dict, zero paths. The graph-leg expansion (`retrieval.py`
calls `graph_client.expand_candidates` over the top fused candidates) resolves the probe's seeds to
`Knowledge` nodes but traverses **zero hops**: a direct `expand_candidates` with the real seeds and
a 5-second budget returns only the 6 depth-0 seeds, and the per-seed census shows the probe's top
code seeds carry **no allowlisted neighbors reachable under the empty-scope legacy-only ACL**
(`NOT (m:ModuleVersion OR m:SymbolVersion)` — the graph's Knowledge↔code edges run to versioned
`ModuleVersion`/`SymbolVersion` nodes, which the empty-scope default refuses to traverse). The
k4 resolution target is real: the consumer writes `Knowledge` nodes and lineage edges only
(`kb_worker.py`), the code edges live on versioned nodes that the empty-scope ACL excludes, and the
graph leg therefore returns zero paths for a broad-scope query.

**PASS** — graph_paths is 0 on both probes, with the neo4j consumer state and the leg's
traversal-ACL cause measured and recorded for k4.

---

## 3. Preregistered run criteria (what the later phases owe)

The k0 mandate is a pin; the wave's proof criteria are preregistered here per the spec's hard rules
so k6/k7 can be measured against fixed targets rather than asserted after the fact:

| Criterion (hard rule) | Measured at k0 pin | Target after the wave |
|---|---|---|
| (1) emit_self DEFAULT ON for spec runs | **OFF** (Edge 1 PASS — `rag_params.get("emit_self")` gate at `workflow_runner.py:3421`) | k1: default-on, opt-out explicit; k6 runs a real phase with DEFAULT settings |
| (2) the finding text is a one-liner | **one-liner** (Edge 2 PASS — `knowledge_ingestion.py:485-488`) | k1: enriched — status, tests verdict, tests_passed/total, cost, commit sha, conclusion |
| (3) wave conclusions in the KB | **absent** (Edge 3 PASS — 0/64 finding rows mention control_db_evidence / split_run) | k2: backfilled deterministically, rerun-safe keys, from the review artifacts |
| (4) findings outrank code for findings queries | **code first** (Edge 4 PASS — 61 selected: 21 code + 40 empty; top-6 all code) | k3: a phase-objective query returns findings/reviews above bare code; k6's probe returns the control_db_evidence finding in the top results |
| (5) graph_paths > 0 OR documented down | **0** (Edge 5 PASS — both probes `{}`, cause = empty-scope traversal ACL + versioned-node edges) | k4: paths OR an honest documentation-down with the consumer evidence |

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each is either an expected first-run property or a measured
nuance a later phase must consume; none is a FAILED edge.

**D-1 — the probe-time corpus has grown; the shape holds, the row counts drift.** The spec's
`current_state` quotes the 2026-09-02 probe census (40,992 registry rows / 38,680 facts / 40,992-row
registry). At this pin the live registry is **41,025 rows / 38,713 facts** (+33 rows during the
measurement window — a bursty live writer). The 64 finding shells, the 0 finding-row keyword hits,
the 21+40 source mix (61 selected), and `graph_paths {}` are unchanged; only the fact/registry totals
moved. K2/k4 must key off structure (source_type, lifecycle_state, entity lineage), never a row-count
constant.

**D-2 — the two "empty-source_type" populations are distinct phenomena.** Retrieval's 40/61
empty-source_type candidates (Edge 4) are store-metadata records with no `source_type` property
(`_source_type` → `""`), while the registry's 1,194 missing-key rows are supersede predecessor thin
rows (no `source_type`, no `logical_locator`, no `source_uri`). K4 must treat them separately: the
retrieval-side fix lives in the fusion/source-typing path, the registry-side in the consumer's thin-row
write.

**D-3 — "finding records are empty shells" refers to the registry + the finding layer's ABSENCE of
distilled conclusions, not to artifact bodies.** The registry's 64 finding rows are metadata-only by
registry design (no text column); the 868 `kb/<id>.json` finding artifacts DO carry non-empty one-line
texts — but they are the old measured-finding/v1 experiment summaries, none of which mention the waves.
The gap the wave closes is the missing DISTILLED layer (phase conclusions, adversarial verdicts, the
17-spec shift), not empty bytes.

---

## 5. Scope compliance

The phase mandate (k0 prompt): write this preregistration carrying the pin + the five verified
edges, then commit with the `[workflow] k0_pin_spec — <goal prefix>` subject.

- **Created/rewritten:** `docs/reviews/kb_finding_layer_preregistration.md` (this file) — the pin
  for this run.
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `git diff`, `grep`, `sed`, `yaml.safe_load`, read-only registry parses, read-only retrieval
  probes, read-only Neo4j/Redis queries against the machine-local state at the main checkout. No KB
  writes, no publishes, no flushes, no mutations.
- **Not done, deliberately:** the code anchors (`workflow_runner.py:3421`, `derive_phase_record`)
  were left unrepaired — they are the wave's own k1 targets, and editing them here would defeat the
  pin. The `run.log` modification in the working tree is a runner artifact, untouched and unstaged.

---

## 6. Verdict

| # | Mandate edge (as stated) | Status at launch |
|---|---|---|
| 1 | emit_self defaults OFF (`workflow_runner.py:3421` gates on `rag_params.get("emit_self")`) | **PASS** — gate + `rag_params: dict \| None = None` default + no `rag:` block in this spec; `run_workflow.py` passes no rag_params |
| 2 | the finding text is a one-liner | **PASS** — `knowledge_ingestion.py:485-488` builds a single `<goal[:40]> phase <phase> -> test_executed_success <bool>, cost $<c>, tokens <n>` line |
| 3 | finding records are empty shells + wave conclusions absent | **PASS** — 64 finding rows, 0 with text/keywords; all 133 control_db_evidence/split_run mentions are fact rows; the findings-layer distilled conclusions are absent |
| 4 | retrieval returns code/empty-type records for a findings query | **PASS** — the 2026-09-02 probe reproduced exactly: 61 selected, `{'code': 21, '': 40}`, top-6 all code |
| 5 | graph_paths 0 | **PASS** — both probes `graph_paths: {}`; kb-neo4j-v1 caught up (lag 0); seeds resolve but traverse zero hops under the empty-scope legacy-only ACL (cause recorded for k4) |

**k0 verdict: all five mandate edges PASS — every open gap this wave exists to close is verified
open at the pin, with code + live-KB evidence, none asserted.** This is the expected first-run
result: the wave targets real, measured state. The preregistered targets in §3 give k1–k6 fixed
criteria to invert, and the D-series notes give k2/k4 the structural distinctions they must not
conflate. The mandate is anchored: spec SHA256
`ea21ccecbd0a4f696100ae982dc184c7bc35c1227894e7ec6a10b53a8d67b62d` at git
`64d1ded099e5f3ed3a25f1d356fa8783265c6446`, machine-local KB state at the main checkout
(`aeb1850d4`). `k1_emit_default_on` may proceed.
