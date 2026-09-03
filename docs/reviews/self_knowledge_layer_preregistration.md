---
status: accepted
kind: preregistration
spec: self_knowledge_layer
phase: s0_pin_spec
run: run-c8d98f56a124
generated_at: 2026-09-03T19:53:53Z
---

# Preregistration — `self_knowledge_layer` (s0_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
wave executes (`s1a_session_record_type`, `s1b_close_writer`, `s1c_open_reader`, `s2a_decision_command`,
`s2b_verified_command_emission`, `s3a_wave_verdict_type`, `s3b_wave_verdict_emission`, `s4a_belief_record_type`,
`s4b_belief_update`, `s4c_belief_seeds`, `s5a_scoreboard_aggregation`, `s6a_reflection_type_append`,
`s6b_reflection_read`, `s7_adversarial`, `s8_test_gate`). Its purpose is twofold, and both halves
are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the premises, do not assert them.** The six edges this wave builds on are stated as
   current-state claims in the s0 prompt (authored 2026-09-03): meta_session records are
   embryonic, no decision records exist, wave verdicts are re-derived (no narrative record at run
   completion), no belief records with n_confirm/n_disconfirm, no scoreboard, no reflection
   series. This phase re-derives each edge against the actual code AND the machine-local state at
   the MAIN checkout (per the mandate's "DB LOCATION") and records the command that produced the
   evidence, so a reader can reproduce every finding without trusting this document. **An edge
   that does not hold is a FAILED finding.** If a claim could not be reproduced after THREE
   attempts, the deviation was to be recorded and the claim FAILED — never looped.

No claim below was accepted on the spec's authority. Every edge was verified with a live probe at
`2026-09-03T19:48–19:53Z`, against the code at the worktree HEAD and the machine-local KB/control
state at the main checkout. All six edges **PASS** — each reproduced the spec's current-state
claim with measured evidence. The evidence is quoted so the adversarial phase (s7) can re-run
every probe.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/self_knowledge_layer.yaml` |
| Spec **SHA256** | `74d2f10ab597219512deac3ddad36d8f794e3e0087000ed78279c6725fa7111c` |
| Spec size | 24,501 bytes |
| Worktree HEAD (git sha) | `30f6b39fe55e6df0ea6b237e28b547cc4819aed3` — the executing worktree `/tmp/wt_selfk` runs this phase |
| Main checkout HEAD | `30f6b39fe55e6df0ea6b237e28b547cc4819aed3` (`spec index regenerated post-wave-4 (the narrator fired on the shift)`) — the machine-local state host; **identical to the worktree HEAD** |
| src/scripts parity | identical — `git diff 30f6b39fe…HEAD -- src/ scripts/` is empty (the wave's code anchors are the same bytes in the worktree and at main) |
| Run (this phase) | `run-c8d98f56a124` — `self_knowledge_layer`, `state: running`, started `2026-09-03T19:48:30.393936Z`, model `deepseek/deepseek-v4-flash`, orchestrated by `run_workflow.py` |
| Workflow revision id | `a800c96df4eab5a9180d71d28cb07f4d2d6a10f65ab9971386c3520fd8e08dcb` |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local, main checkout), `schema_version: 4`, `control_epoch: 171` |
| KB machine-local state | main checkout `/home/drseuss/ai-finops-framework/experiments/results/registry_index.jsonl` (40,950 rows at probe) + `kb/<id>.json` (19,483 artifacts) + Redis 6380 db 2 + Chroma `localhost:8000` + Neo4j `bolt://localhost:7687` |
| Goal prefix | `Build loop 2 — the machine learning about itself operating (the self-knowledge layer)` |
| Pinned at | 2026-09-03T19:53:53Z |

Reproduce the pin — these are the EXACT bytes the run executes:

```bash
sha256sum workflows/repository/self_knowledge_layer.yaml
# 74d2f10ab597219512deac3ddad36d8f794e3e0087000ed78279c6725fa7111c
git rev-parse HEAD          # in the executing worktree /tmp/wt_selfk
# 30f6b39fe55e6df0ea6b237e28b547cc4819aed3
```

If either value differs when s7 (adversarial) or s8 (test gate) runs, the spec was edited mid-run
and the mandate this document pins is no longer the mandate being executed.

**Spec shape at the pin** — seventeen phases, all `kind: agent` except the terminal `s8_test_gate`
(`kind: test`):

| # | Phase | kind | scope |
|---|---|---|---|
| 0 | `s0_pin_spec` | agent | `implementation` |
| 1 | `s1a_session_record_type` | agent | `implementation` |
| 2 | `s1b_close_writer` | agent | `implementation` |
| 3 | `s1c_open_reader` | agent | `implementation` |
| 4 | `s2a_decision_command` | agent | `implementation` |
| 5 | `s2b_verified_command_emission` | agent | `implementation` |
| 6 | `s3a_wave_verdict_type` | agent | `implementation` |
| 7 | `s3b_wave_verdict_emission` | agent | `implementation` |
| 8 | `s4a_belief_record_type` | agent | `implementation` |
| 9 | `s4b_belief_update` | agent | `implementation` |
| 10 | `s4c_belief_seeds` | agent | `implementation` |
| 11 | `s5a_scoreboard_aggregation` | agent | `implementation` |
| 12 | `s6a_reflection_type_append` | agent | `implementation` |
| 13 | `s6b_reflection_read` | agent | `implementation` |
| 14 | `s7_adversarial` | agent | `adversarial_readonly` (pro, `run_model: deepseek/deepseek-v4-pro`) |
| 15 | `s8_test_gate` | test | `implementation` |

---

## 2. Verified current-state edges (re-derived against code + the machine-local KB)

Each edge is stated as the s0 prompt claims it, then **independently re-derived**. The verdict
legend is stated up front so no status is misread:

- **PASS** — the mandate's claim describes the state measured at the pin. The gap the wave was
  built to close is OPEN, verified with code + live-state evidence. In a first-run pin this is the
  expected, positive result: it confirms the wave is targeting real state, not asserted state.
- **FAILED** — the mandate's claim does not hold as stated. Recorded with the deviation and the
  true state, per the "an edge that does not hold is a FAILED finding" rule.

Every probe below ran read-only from the main checkout (the machine-local KB + control host).

### Edge 1 — meta_session records are embryonic (inspect one)

*Claim.* The ledger carries 27 `meta_session` records (the design doc: *"`meta_session` records
exist (27, embryonic)"*). They are embryonic: legacy per-attempt ledger lines classified
`[meta_session]` by title, carrying none of the session-spine content (no session_date, slug,
waves_run, merged, parked, open_threads, self_notes).

*Method (registry census + one full artifact + the producer code).*

```bash
cd /home/drseuss/ai-finops-framework   # the machine-local KB host
python3 - <<'EOF'
import json
from collections import Counter
rows=[json.loads(l) for l in open('experiments/results/registry_index.jsonl')]
m=[d for d in rows if d.get('source_type')=='meta_session']
print('meta_session rows:', len(m))
print('observed_at dates:', dict(Counter(d.get('observed_at','')[:10] for d in m)))
print('all source_uri meta_session:', all(d.get('source_uri','').startswith('meta_session:') for d in m))
print(json.dumps(m[-1], indent=1))
EOF
cat experiments/results/kb/b76129c30446cc35d0ae4616819183e1ba30bb099688b080801c644392765af2.json
```

*Evidence.*

```
meta_session rows: 27
observed_at dates: {'2026-08-19': 27}
all source_uri meta_session: True
{ "knowledge_id": "b76129c3…", "source_type": "meta_session",
  "logical_locator": "c44546d45c55c510_1", "source_uri": "meta_session:c44546d45c55c510_1", … }
```

The inspected artifact body (`kb/b76129c3…392765af2.json`):

```json
{"acl_scope": "public", "authority": "ADVISORY", "evidence_class": "[H]",
 "extractor_version": "ledger/v1", "source_type": "meta_session",
 "logical_locator": "c44546d45c55c510_1", "source_uri": "meta_session:c44546d45c55c510_1",
 "repository_id": "agentic-dynamics",
 "text": "attempt c44546d45c55c510_1 [meta_session]: tokens=661 cost=0.001252412 confidence=None",
 "confidence": null, "test_executed_success": null, "token_count": 6, …}
```

The producer (`ledger_ingestion.py:201-263`, `build_attempt_record`): `classify_session(title)`
routes any `meta_`-prefixed session title to `source_type=meta_session` (`:232`), and the text is
one ledger line — `text = f"attempt {attempt_id} [{source_type}]: tokens=… cost=… confidence=…"`
(`:243`); authority `ADVISORY` / `[H]` when meta. A repo-wide grep for the spine content fields
confirms they exist nowhere in code:

```
src grep "waves_run|open_threads|self_notes|session_date": 0 matches (only meta_session
classification in knowledge.py:139 + ledger_ingestion.py)
```

The inspected record is a token/cost ledger line with `confidence=None` and an in-memory
`meta_session:<attempt_id>` identity — no session story, no decisions, no threads, no self-notes.
**PASS** — meta_session records are embryonic; one inspected end-to-end (registry row + artifact +
producer line) shows the legacy shape the s1a session-record type must replace.

### Edge 2 — no decision records exist

*Claim.* There are no decision records — nothing records the AIO's decisions (what was decided,
why, the alternatives weighed) at the moment of decision.

*Method (the full source-type census + a code-wide producer search + an on-disk artifact audit).*

```bash
python3 - <<'EOF'
import json
from collections import Counter
rows=[json.loads(l) for l in open('experiments/results/registry_index.jsonl')]
print('total lines:', len(rows))
print('source_type counts:', dict(Counter(d.get('source_type') or '<MISSING>' for d in rows)))
print('observation/actuation rows:', sum(1 for d in rows if d.get('source_type') in ('observation','actuation')))
print('rows mentioning aio-decision:', sum(1 for d in rows if 'aio-decision' in json.dumps(d)))
EOF
```

*Evidence.* The 40,950-row registry's source types are exactly `{fact: 38635, spec: 326,
<MISSING>: 1194, story: 330, review: 242, finding: 67, meta_session: 27, context_snapshot: 11,
report: 118}`. **Zero observation rows, zero actuation rows, zero decision rows**, zero rows
mentioning `aio-decision`. A code-wide search finds no decision-record producer:

```
src grep "derive_decision|build_decision|decision_record": 0 matches
```

An on-disk artifact audit (`kb/*.json` with `source_type` in observation/actuation) finds 11
actuation artifacts, but all 11 are Control-Room human-gated **`continue` steers**
(`actuation_kind: continue`, `contract_version: route_next_job/v1`) — none are decisions, and
none are even registry-indexed. **PASS** — no decision records exist (code or data); see D-1 for
the one adjacent seam that does exist and how s2 relates to it.

### Edge 3 — wave verdicts are re-derived (no narrative record at run completion)

*Claim.* When a spec run completes, no narrative verdict record is emitted; the wave's "what
happened and why" is later re-derived (the adversarial review doc, then reading it back at
session boundaries), never written once at the moment of completion.

*Method (the orchestrator's terminal-write path + a registry/artifact search for per-run verdict
rows).*

```bash
grep -n "emit\|ledger\|_control_terminal_write\|verdict" scripts/run_workflow.py | grep -iv "argparse\|--"
```

*Evidence.* The run-completion path is `_control_terminal_write` (`run_workflow.py:798-803`): one
transaction writes the run's terminal state + step-attempt rows + outbox to the control db, and
the run ledger JSON to `experiments/results/workflows/<spec>/<timestamp>.json`. The only KB-adjacent
emissions are the CAP fact outbox payloads (`source_type=fact`) — no verdict, no narrative, no
per-run record carrying `{spec_name, run_id, verdict, cost, phases_total, merge_state, residuals}`.
"verdict" in the runtime source refers exclusively to per-phase gate/test verdicts
(`phase_evidence.py`, `executor.py`, `preexisting_guard.py`) — never a run-level narrative.

The registry carries no per-run verdict rows: the 67 `finding` rows are (a) the old
measured-finding/v1 experiment summaries (`exp_*`, one-line model-under-condition texts), (b) two
`self-wt_wave4_witness` phase findings (the kb_finding_layer k6 witness — per-phase, cell-scoped,
default-on since k1), and (c) one `spec-index-regeneration` narrator row — none is a
run-completion wave verdict. The completed waves' verdicts ("what happened and why") live only in
`docs/reviews/*_adversarial.md`, authored post-hoc in each wave's adversarial phase (e.g.
`kb_finding_layer_adversarial.md` is the merge-verdict carrier for `run-77f7b899f4f8`), and the
AIO re-derives them by reading those docs + ledgers at session boundaries — exactly the
re-derivation the s3 records replace. **PASS** — no narrative verdict record exists at run
completion; wave verdicts are re-derived.

### Edge 4 — no belief records with n_confirm/n_disconfirm

*Claim.* Nothing tracks a hypothesis with confirmation counts / a posterior; no belief record
type or rows exist.

*Method.*

```bash
grep -rn "n_confirmations\|n_disconfirmations\|posterior_confidence\|derive_belief_record\|n_confirm\|n_disconfirm\|belief\|posterior" src/ scripts/
```

*Evidence.* **0 matches in src/ and scripts/** for the belief vocabulary (including bare
`belief` / `posterior`). The registry census (Edge 2) shows no `belief` source type and no rows of
any belief shape. The Bayesian vocabulary (`n_confirmations`, `n_disconfirmations`,
`posterior_confidence`) exists today only in the design doc (`docs/designs/proposed/self_knowledge_layer.md`)
and the instruction surfaces that cite it — never in code. **PASS** — no belief records with
n_confirm/n_disconfirm exist.

### Edge 5 — no scoreboard

*Claim.* No measured scoreboard exists — nothing aggregates waves / merge rate / adversarial-
finding rate / cost per wave into measured rows.

*Method (the CLI command table + a repo-wide search + the L0 board's own contents).*

```bash
# the full _COMMANDS table in src/agentic_dynamics/cli.py:21-150 (read, not grepped)
grep -rln "scoreboard" src/ scripts/
grep -c "merge_rate\|cost.*wave\|adversarial.*rate" agent_config/system_snapshot.md
```

*Evidence.* The `_COMMANDS` table (`cli.py:21-150`) has **no** `scoreboard` (and no
`session`/`decision`/`reflect`) subcommand — the full leaf set is experiment/story/workflow/
queue/analyze/data/knowledge/registry/review/spec/validate/supervise/control/publish/usage/
release/surfaces/docs. `scoreboard` matches **0 files** in `src/` and `scripts/`. The L0 board
(`agent_config/system_snapshot.md`) carries 0 rows shaped like the scoreboard's measured metrics
(`merge_rate` / cost-per-wave / adversarial-finding-rate → grep count 0) — it is the controller's
permanence board (spec lifecycle counts, run state, worktrees awaiting), not the s5 scoreboard.
No scoreboard JSON exists under `experiments/results/`. **PASS** — no scoreboard exists.

### Edge 6 — no reflection series

*Claim.* No session-keyed reflection series exists — nothing a session appends its self-notes to
across sessions.

*Method.*

```bash
grep -rln "reflection\|reflect" src/ scripts/     # the record type / producer / command
ls tests/ | grep -iE "reflection"                 # the gate file (must not pre-exist)
```

*Evidence.* `reflection` / `reflect` match **0 files** in `src/` and `scripts/`; no `reflect`
subcommand in `cli.py`; no `test_reflections.py` (nor any of the six gate files) pre-exists; the
only "reflection" under `experiments/results/` is a Python-`reflection`(PRAGMA) remark inside a
story-review text — unrelated. **PASS** — no reflection series exists.

---

## 3. Preregistered run criteria (what the later phases owe)

The s0 mandate is a pin; the wave's proof criteria are preregistered here per the spec's hard
rules so s6/s7 can be measured against fixed targets rather than asserted after the fact:

| Criterion (hard rule) | Measured at s0 pin | Target after the wave |
|---|---|---|
| (1) meta_session is embryonic | **embryonic** (Edge 1 PASS — 27 rows, ledger-attempt text, no spine fields) | s1a: a session record TYPE with `{session_date, slug, waves_run[], merged[], parked[], open_threads[], self_notes}`; s1b close writes one; s1c open reads the last back |
| (2) no decision records | **absent** (Edge 2 PASS — 0 decision/observation/actuation registry rows; no producer) | s2a: a `decision record --what/--why/--alternatives/--category` command; s2b: automatic emission at the promote/publish call sites |
| (3) wave verdicts re-derived | **re-derived** (Edge 3 PASS — no narrative at run completion; verdict lives in docs/reviews) | s3a/s3b: a completed spec run emits its wave-verdict record (verdict, cost, phases, findings count, merge state) — default-on, failures emit too |
| (4) no belief records | **absent** (Edge 4 PASS — 0 belief vocabulary in src/scripts) | s4a/s4b/s4c: belief records with n_confirm/n_disconfirm updated in place (two confirms → ONE record n=2), seeded from the measured history |
| (5) no scoreboard | **absent** (Edge 5 PASS — no command, no rows; L0 board has no measured rows) | s5a: `scoreboard [--recompute]` aggregates the s3 records into measured rows — never hand-written totals |
| (6) no reflection series | **absent** (Edge 6 PASS — no type, no command, no series) | s6a/s6b: session close appends a session-keyed entry; `reflect --read` renders the accumulated series |

The s7 adversarial phase additionally owes the actor-layering probe (can a workload/cell-scoped
retrieval resolve the AIO's private org:repo records?) and the k1 default-on probe (is ANY
producer opt-in?) against the built wave — both preregistered targets of this wave, measured here
only as their absence (edges 2/4/5/6 record types do not exist at all).

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each is either an expected first-run property or a measured
nuance a later phase must consume; none is a FAILED edge.

**D-1 — a5 (`aio_emission.py`) already emits permanence-decision OBSERVATIONS at the verified
commands; zero have ever landed, and they are not the s2 decision record.** Wave-3 a5
(`src/agentic_dynamics/control/aio_emission.py`, wired at `scripts/promote.py:141-159,258`,
`scripts/publish_release.py:84-92,485`, `scripts/approve_workflow.py:151-166`) builds + best-effort
publishes `source_type=observation` records (schema `aio-decision/v1`, verbs `promote|publish|
approve`, fields verb/run_id/candidate_sha/operator/status/why) plus `actuation` records linked by
`causes`. This is the closest existing machinery to the s2 decision record and the seam s2b
("automatic decision-record emission at the verified-command call sites") will extend. But: the
registry has **zero** observation/actuation rows and zero `aio-decision` mentions — a5 has
produced no durable decision records — and the a5 observation shape carries none of the s2 fields
(`what/why/alternatives/category`), is not retrievable by category, and has no dedicated command.
Edge 2's claim therefore holds for the s2 decision record as designed; s2 must decide whether to
extend the a5 observation family or mint the category'd record beside it, and must explain why a5
(default-on, authorized, best-effort) has still produced zero rows across multiple permanence
acts — the same "default-on but never produced" failure mode kb_finding_layer's k1 lesson names.

**D-2 — the probe-time corpus has grown since the kb_finding_layer pin; the shape holds, the row
counts drift.** The 2026-09-03T13:39 pin measured 41,025 registry rows / 38,713 facts; at this pin
the live registry is **40,950 rows / 38,635 facts** (the registry was compacted/rebuilt between
the two pins). The 27 meta_session rows, the zero decision/observation/actuation rows, and the
source-type structure are unchanged. Later phases must key off structure (source_type,
logical_locator), never a row-count constant.

**D-3 — the finding layer (kb_finding_layer, merged) is present and does NOT close edges 3/4.** The
wave-4 finding layer made per-phase finding emission default-on (`workflow_runner.py:98,2870` —
`rag_params.emit_self` DEFAULT ON since k1) and added a spec-regeneration narrator. These are
per-phase, cell-scoped findings and regeneration change-records — they are not run-completion wave
verdicts (no verdict/cost/merge_state/residuals) and carry no belief/confirmation structure. Edge
3's gap (and edge 4's) remains open despite the finding layer; s3's emission hook sits at the run
completion terminal write, a different seam.

---

## 5. Scope compliance

The phase mandate (s0 prompt): write this preregistration carrying the pin + the six verified
edges, then commit with the `[workflow] s0_pin_spec — <goal prefix>` subject.

- **Created/rewritten:** `docs/reviews/self_knowledge_layer_preregistration.md` (this file) — the
  pin for this run.
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `git diff`, read-only registry parses, read-only control-db reads, read-only source greps,
  read-only artifact audits. No KB writes, no publishes, no flushes, no mutations, no database
  writes.
- **Not done, deliberately:** none of the six record types / commands / producers were built or
  stubbed — they are the wave's own s1–s6 targets, and building them here would defeat the pin.
  The `run.log` modification in the worktree is a runner artifact, untouched and unstaged.

---

## 6. Verdict

| # | Mandate edge (as stated) | Status at launch |
|---|---|---|
| 1 | meta_session records are embryonic (inspect one) | **PASS** — 27 rows (all 2026-08-19, `meta_session:<attempt_id>` URIs); the inspected artifact `b76129c3…` is a ledger line `attempt c44546d45c55c510_1 [meta_session]: tokens=661 cost=0.001252412 confidence=None`; no spine fields anywhere in src |
| 2 | no decision records exist | **PASS** — 0 decision/observation/actuation registry rows, 0 `aio-decision` mentions, 0 decision-record producers in src; the only on-disk actuations are 11 Control-Room `continue` steers, unindexed (D-1 scopes the a5 seam) |
| 3 | wave verdicts are re-derived (no narrative record at run completion) | **PASS** — `_control_terminal_write` writes control-db rows + ledger JSON + fact outbox only; no verdict/narrative emit; no per-run verdict rows; wave verdicts live in `docs/reviews/*_adversarial.md`, re-derived at session boundaries (D-3 scopes the finding layer) |
| 4 | no belief records with n_confirm/n_disconfirm | **PASS** — 0 matches for the belief vocabulary (`n_confirmations`/`n_disconfirmations`/`posterior_confidence`/`belief`/`posterior`) in src/ or scripts/ |
| 5 | no scoreboard | **PASS** — no `scoreboard` in src/scripts/results; no `scoreboard`/`session`/`decision`/`reflect` CLI subcommand; the L0 board carries none of the measured rows |
| 6 | no reflection series | **PASS** — 0 `reflection`/`reflect` matches in src/ or scripts/; no type, no command, no series, no gate file |

**s0 verdict: all six mandate edges PASS — every open gap this wave exists to close is verified
open at the pin, with code + machine-local-state evidence, none asserted.** This is the expected
first-run result: the wave targets real, measured state. The preregistered targets in §3 give
s1–s6 fixed criteria to invert, and the D-series notes give s2 the a5 seam it must extend (D-1),
s3 the finding-layer boundary it must not conflate (D-3), and every later phase the structural
(rather than count-based) keying it must use (D-2). The mandate is anchored: spec SHA256
`74d2f10ab597219512deac3ddad36d8f794e3e0087000ed78279c6725fa7111c` at git
`30f6b39fe55e6df0ea6b237e28b547cc4819aed3`, machine-local state at the main checkout
(`/home/drseuss/ai-finops-framework`). `s1a_session_record_type` may proceed.
