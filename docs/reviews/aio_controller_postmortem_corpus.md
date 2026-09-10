---
status: accepted
---

# AIO controller postmortem — annotated failure corpus (p0)

**Window:** 2026-09-04 → 2026-09-10 (inclusive).
**Author line:** the AIO Control Agent (the delegated master-session line), on
`/home/drseuss/ai-finops-framework`.
**Role of this document:** the p0 evidence assembler. It lists every identifiable AIO
failure or near-miss in the window, each with a verifiable evidence pointer. It does
**not** classify (p1 taxonomy), audit defenses (p2), or select remediation (p3).

> **Load-bearing rule for this doc:** every item carries at least one evidence pointer
> (a transcript `part@` timestamp, a KB artifact file, a decision-record id, a control-db
> row, a commit sha, or the recording-sweep audit). Items without a pointer are listed
> under *Unverified* and are excluded from the p1 taxonomy. This corpus has **19 verified
> items** and **0 unverified items**; nothing was excluded.

---

## 1. Evidence surfaces mined

| # | Surface | What was mined | Where it lives |
|---|---|---|---|
| a | Session closes + reflections | 9 `session/v1` `meta_session` closes (2026-09-03…09-09) + 9 `reflection/v1` self-note entries | `experiments/results/kb/*.json` (extractor `session/v1`, `reflection/v1`) |
| b | Decision records | 42 `decision/v1` records: 27 backfilled permanence (08-30→09-04), 4 other controller records (merge/bookkeeping/model), 2 `verified_command` promotes, 3 `recording-sweep` day backfills (08-27/28/29), 6 AIO acts backfilled on 09-09 | `experiments/results/kb/*.json` (extractor `decision/v1`) |
| c | Control DB | `runs`, `run_transitions` (102 rows), `step_attempts` (103 rows), `outbox`, `approvals`, `promotions` | `experiments/results/control/control.db` |
| d | Git | first-parent main history, all-refs commit shapes, `git reflog --all`, `git stash list` | `/home/drseuss/ai-finops-framework` |
| e | opencode transcripts | `ses_f92f8804affe…` (the hammer) and `ses_f95ece514ffe…` (the author line, 09-08→09-10 slice) | `~/.local/share/opencode/opencode.db` |
| f | Recording-sweep audit | deterministic coverage scan (commit-days vs decisions/closes) + phantom-claim detector | `experiments/results/recording/audit.json`; engine `scripts/recording_sweep.py` |

**Time-zone convention.** Transcript `part@` times are local (CEST, UTC+2). Git commit
dates and control-db transitions are UTC (Z-suffixed in the raw store); where a date is
close to midnight both forms are given. KB `decided_at` values are UTC.

**Severity scale.** 1 = cosmetic; 2 = local waste/re-work, caught and corrected; 3 =
sustained degradation or a record-layer lie that misled later turns; 4 = destructive
operation with recovery cost, or a public/durable surface broken for days; 5 = data loss
or permanent confusion.

---

## 2. Corpus summary

| ID | Date (window) | Session / run | Failure / near-miss, one line | Sev | Pointer type | Kind |
|---|---|---|---|---|---|---|
| F-01 | 09-04 17:26 → 09-05 17:56 | `ses_f92f8804affe…` (hammer) | Large stabilization wave done entirely in the main worktree, never committed; session abandoned, never closed | 4 | transcript + commit | act / near-miss |
| F-02 | 09-04 17:44 → 09-05 17:56 | `ses_f92f8804affe…` (hammer) | Rabbit-holed ~19h on registry repair without a commit or controller check-in | 3 | transcript | act |
| F-03 | 09-04 17:07 | main `9e4773fb1` (AIO/instrument) | Promote close-out merge replaced the append-only registry with the stale branch copy — **−43,311 rows** (the "Sep-4 drain") | 5 | commit + transcript | act |
| F-04 | 09-08 17:05 | `ses_f95ece514ffe…` (author line) | Registry dedup over-deleted 28,192 rows incl. legitimate tombstone/supersede markers; restored from a stash | 4 | transcript | act |
| F-05 | 09-04 → 09-09 | publication chain | Publication pipeline RED 5 days (407 unresolvable rows); 402 mis-registered rows later tombstoned; CI test had no resolution assertion | 4 | commit + close | defense gap / inherited |
| F-06 | 09-08 23:23 | `ses_f95ece514ffe…` | `git add -A` ran before the `.gitignore` line landed → re-tracked 32,311 files; caught and `rm --cached` again | 3 | transcript + commit | act |
| F-07 | through 09-08 23:14 | author line | opencode per-turn snapshots indexed the 1.6 GB tracked results tree (2.5 GB store) → repeated web-UI freezes | 3 | transcript + decision | environment / degradation |
| F-08 | 09-08 21:45Z → 09-09 01:11 | `ses_f95ece514ffe…` | Phantom self-test emitter registered 3 double findings (no stream event); ~1.3 h tracing, never identified | 3 | transcript + close | act / unresolved |
| F-09 | 09-04 ↔ 09-09 | AIO record layer | Consequential acts unrecorded at the moment (zero decision records until backfill; repeated next night) despite live machinery | 3 | decisions + closes | act / discipline |
| F-10 | 09-08 (surfaced) | session spine | `close_seq` slug-lexicographic tiebreak made `session open` read the *morning* 09-08 close instead of the afternoon's | 3 | commit + decision | defect / near-miss |
| F-11 | 09-04 14:16–15:32 | `run-f822d6ecd88b`, `run-426ca19fe025`, `run-17cc8e4e1e01`, +9 | Stale promotable rows + 9 merged rows not progressed to published — `promote.py` did not close its own rows | 3 | control rows + decision | act |
| F-12 | 09-09 23:45 → 09-10 00:09 | `run-d713e0c61620`, `run-2a19746f4106` | Two specs launched before the worktree existed → `running` zombie control rows for ~23 min, $0, no phases | 2 | control rows | mechanism gap |
| F-13 | 09-10 02:10–02:11 | `ses_f95ece514ffe…` | Hand-rolled `scripts/launch_workflow.py` written then deleted on review ("inventing a third launcher") | 2 | transcript | act |
| F-14 | 09-10 01:22–01:27 | `ses_f95ece514ffe…` | Spec-wrapper over-delivery: a zero-model engine got an agent-task spec + portal routes + nightly timer | 2 | transcript + commit | act |
| F-15 | 09-08/09-09/09-10 | `ses_f95ece514ffe…` | Repeated wrong-script / wrong-selection runs corrected mid-flight (future-mtime filter, `rg` absent, full-suite pytest, foreground heavy runs frozen the UI) | 2 | transcript | act |
| F-16 | whole window | author line | Large data/permanence operations performed directly on the `main` checkout (no worktree/promote path; `enforce_admins:false`) | 3 | commits + close | act / systemic |
| F-17 | discovered 09-04 | control/fleet containers | `kb-neo4j` container mounted a stale overlay that shadowed the live corpus → 9,121 silent dead-letter errors; chromadb was non-volume-backed | 4 | close + reflection | environment defect |
| F-18 | 09-04 (discovered) | `kb_worker` | Idle-exit footgun left a healthy caught-up daemon DEAD after 12 empty polls; 703 ghost heartbeat keys (no TTL) | 2 | close + reflection | defect |
| F-19 | 09-10 01:27–01:56 | `f7d9ebe42` + `24837b7d0` | Recording-rail commits regenerated `experiments/specs/index.json` (192) but left README at 191 → `test_doc_lifecycle` gate fails | 2 | commit + test | convention miss |

Additional verified sub-findings folded into their parent items rather than double-counted:
the 4-day main-branch git gap (F-01); the two-stage migration mishap where stage-1
committed 6 run ledgers into the tree stage-2 untracked 13 min later (F-06); the
`approvals` table being empty and 9 "published" runs having zero publication receipts
(F-11); and the concurrent-session single-writer hazard (F-16).

---

## 3. Item detail

### F-01 — The hammer session left a large stabilization wave uncommitted and was abandoned
- **Date:** 2026-09-04 17:26 → 2026-09-05 17:56 (local).
- **ID:** `ses_f92f8804affe6ZZ0lH27Benpvc`, title *"New AIO: where to start"*.
  (The prompt's shorthand `ses_f92f8804affe` is the truncated id.)
- **What happened.** Hired to "pick up a new aio… where we need to start", the session
  diagnosed and fixed real defects — `knowledge_stream.py` (redis-py≥8 `socket_timeout=None`
  for the 10 s blocking `XREADGROUP`), `scripts/fleet/heartbeat.py` (heartbeat TTL),
  plus their tests, a `ruff check . --fix` pass over the whole surface (46 auto-fixed + 28
  hand-fixed), a restored `registry_index.jsonl` (48,321 lines), a regenerated
  `data_manifest.json` (18,387 entities) and 8 regenerated labs. Then `build_data.py`
  hard-aborted on unresolvable `finding` payloads, the controller asked *"woah! what are
  you working on?"*, the model wrote an A/B/C fork message and stopped
  (`step-finish reason=stop`) — **no further part, no commit, no close**.
- **What should have happened.** The documented loop: finish the unit of work, commit it
  (or park it explicitly), and write the session close (`session_close.py`) — the doctrine
  is "a session that does not write its close record has not closed". A wave of this size
  should have been checkpointed incrementally rather than left only in the working tree.
- **Damage / cleanup cost.** `origin/main` untouched but the local main checkout left
  **~237 files dirty** for 4 days (the retained opening `git status` part
  `ses_f92f8804affe… part@2026-09-04 17:26:48`, counted: 1 modified + 236 untracked — the A5
  correction of the earlier unsupported "~292" estimate); the durable
  registry restore and manifest/labs existed nowhere in git. Recovery required the 09-08
  session to walk the hammer's 133-command trail, separate the ~35 source/test files from
  generated churn, re-verify, and only then
  commit `bb47441bc` (51 files, +124/−73). The 4-day window (09-04 17:07 → 09-08 17:03)
  has **zero git activity on any ref or stash**.
- **Severity:** 4 (near data loss; the restored registry could have been lost with the
  working tree; large recovery cost).
- **Evidence pointers.**
  - `opencode.db ses_f92f8804affe6ZZ0lH27Benpvc part@2026-09-04 17:26:48` — the opening
    `git status`/`git worktree list`/`git log` part (`prt_06d0793c6001c5VS663QZ6oYh4`),
    the primary evidence for the dirty-tree size: the status body holds exactly **237
    tab-prefixed entries = 1 `modified:` + 236 untracked paths** (A5).
  - `opencode.db ses_f92f8804affe6ZZ0lH27Benpvc part@2026-09-04 17:42:08` (edit
    `knowledge_stream.py`); `part@2026-09-04 17:44:09/15` (`heartbeat.py`);
    `part@2026-09-04 23:04:53` (registry restore to 48,324 lines).
  - `part@2026-09-05 17:55:59` (final A/B/C message) and `part@2026-09-05 17:56:04`
    (last part; `step-finish reason=stop`).
  - Commit `bb47441bc` subject: "machine state: stabilization wave — … (session 2026-09-04
    evening, verified + finished here)" (09-08 17:03).
  - `docs`-external: `git log --first-parent main` shows no commit between `9e4773fb1`
    (09-04 17:07) and `bb47441bc` (09-08 17:03).

### F-02 — Rabbit-hole: ~19 h of registry repair with no commit or controller check-in
- **Date:** 2026-09-04 17:44 → 2026-09-05 17:56.
- **ID:** `ses_f92f8804affe6ZZ0lH27Benpvc`.
- **What happened.** What the controller framed as "get github green" (CI red ~5 days)
  became a registry-recovery operation: after discovering the `9e4773fb1` truncation
  (F-03) the session spent the next ~19 h restoring the registry, regenerating the
  manifest and re-running all 8 labs, then hit the `build_data` waiver wall. Controller
  signals escalated throughout — *"what is going on"* (21:15), *"are you sure you're
  running the right stuff?"* (23:01), *"everything is ok?"* (09-05 17:55), *"woah! what are
  you working on?"* (17:55:45).
- **What should have happened.** Check in / checkpoint at scope changes: the doctrine has
  no standing rule that a task may silently expand from a lint cleanup into a data-loss
  recovery; a checkpoint commit or an explicit ask should have preceded hours of repair.
- **Damage / cleanup cost.** 19 h of a session whose output was never committed (F-01);
  the controller's confidence in the session visibly degraded; the actual build_data
  blocker was correctly escalated only at the very end.
- **Severity:** 3.
- **Evidence pointers.** `opencode.db ses_f92f8804affe… part@2026-09-04 21:15:03`,
  `part@2026-09-04 23:01:13`, `part@2026-09-05 17:55:01`, `part@2026-09-05 17:55:45`,
  and the final `part@2026-09-05 17:55:59`.

### F-03 — The "Sep-4 drain": a close-out merge deleted 43,311 registry rows
- **Date:** 2026-09-04 17:07 (UTC commit stamp 09-04 17:07:46).
- **ID:** main commit `9e4773fb1` (AIO/instrument acting on `main`).
- **What happened.** The merge that closed the `promote_row_closeout` campaign
  ("squash 4d34e542b") resolved `experiments/results/registry_index.jsonl` to the
  promote-branch's stale copy instead of unioning the append-only log: the file went
  **48,321 → 5,011 rows**, dropping all 330 story rows, all 242 review rows and ~94 % of
  fact rows. `git diff --numstat 9bdb74059 9e4773fb1 -- experiments/results/registry_index.jsonl`
  = `1 43311`.
- **What should have happened.** The recorded lesson (from the same window): *"the
  registry_index.jsonl conflict (both sides appended) resolved by union+dedupe — append-only
  logs need union merges."* A machine-state merge of an append-only log must union, never
  take one side.
- **Damage / cleanup cost.** It is the root of F-05 (publication RED), the `~43k lost rows`
  the hammer spent the night restoring, and the "Sep-4 drain" mis-registrations that were
  only tombstoned on 09-09. The hammer restored the working-tree file (F-01), but the
  committed history remained drained until the data plane was untracked (09-08 23:27).
- **Severity:** 5 (registry data loss from `main` + persistent confusion carried for days).
- **Evidence pointers.** Commit `9e4773fb1`; the `git diff --numstat` above;
  `opencode.db ses_f92f8804affe… part@2026-09-04 23:04:53` and the final message
  `part@2026-09-05 17:55:59` ("went from 48,321 → 5,011 rows … every story row, every
  review row, ~94% of fact rows deleted"); close `session:2026-09-08-aio-publication-closure`
  ("the 407-row unresolved-registry defect", "the Sep-4 drain").

### F-04 — Registry dedup over-deleted lifecycle marker lines (48,324 → 20,132)
- **Date:** 2026-09-08 17:05 (dedup) → 17:24 (self-caught + restore), local.
- **ID:** `ses_f95ece514ffepgDiA2t92Y7YD4` ("Starting aio control").
- **What happened.** To shrink the registry the session ran a dedup keyed on
  `(entity_id, knowledge_id)` dropping 28,192 rows. That grain treats a tombstone/supersede
  marker line as a duplicate of the row it points at — deleting the canonical Aug-21
  tombstones of the ten payload-less stories and un-tombstoning them ("that's why the 3
  'missing' stories resurfaced"). It then self-reported *"my dedup was wrong"*, restored
  the intact registry via the still-present stash object's tree, and re-deduped by
  **full-row equality** (0 rows dropped).
- **What should have happened.** The safe grain for this store was already known/stated in
  the same file's history: full-row equality is the only safe dedup grain for the registry;
  a knowledge_id is shared by design across a version chain (supersede/delete markers).
- **Damage / cleanup cost.** ~20 min of destructive-store recovery; the restore depended on
  an unrelated *rebase-stash* object (09-04 17:07) still holding the pre-drain registry —
  pure luck of a never-popped stash. If it had been dropped, ~28k rows of lineage markers
  would have had to be rebuilt.
- **Severity:** 4.
- **Evidence pointers.**
  - `opencode.db ses_f95ece514ffe… part@2026-09-08 17:05:36` (dedup; output
    `48324 -> 20132 rows (28192 exact duplicates dropped…)`).
  - `part@2026-09-08 17:24:03` ("**Found the collateral damage — my dedup was wrong.**
    Tombstone/supersede marker lines share the knowledge_id with their target…").
  - `part@2026-09-08 17:24:17` (`git checkout stash@{0} -- experiments/results/registry_index.jsonl`
    → `48321` lines; `48321 -> 48321 (0 full-row byte duplicates dropped)`).
  - Corroboration: `git stash show stash@{0} --stat` (stash tree != deduped file);
    close `session:2026-09-08-aio-publication-closure` and reflection `47e81a516f936e`
    ("my own earlier registry 'dedup' (48k->20k rows) over-deleted…").

### F-05 — Publication pipeline RED for 5 days; CI contract test had no resolution assertion
- **Date:** 2026-09-04 (from the drain) → 09-09 00:23 (`ddbca7545`).
- **ID:** publication chain + CI guard.
- **What happened.** From the drain the committed registry could not resolve 407 `finding`
  rows to measurement payloads, so `build_data.py` refused to publish for days. The CI
  "publication-contract" test never caught it because it only checked `data.js`-vs-manifest
  *identity*, not *resolution*. On 09-08 23:49 a publication snapshot (`77eb6c0b3`,
  +92,827 lines) was committed carrying the mis-registered state; 34 min later
  `ddbca7545` tombstoned the **402 mis-registered finding rows** (wave/self-test/review-doc
  + payload-less exp cells) and regenerated labs + manifest + data.js, achieving
  "build_data clean (0 unresolved) for the first time since the Sep-4 drain".
- **What should have happened.** A publication contract gate that asserts *resolution*
  (each registry row maps to a readable payload or a sanctioned waiver/tombstone), not just
  `data.js`↔manifest identity; and a landing gate that never commits a publication surface
  regenerated against a known-broken corpus.
- **Damage / cleanup cost.** 5 days of publication red + a tombstone campaign (402 rows);
  the website data surface was stale/misleading; two commits (`77eb6c0b3`, `ddbca7545`)
  and a fixture/CI hardening chain were spent on the repair.
- **Severity:** 4.
- **Evidence pointers.** Commit `ddbca7545` (subject + body); close
  `session:2026-09-08-aio-publication-closure` (kb artifact `80fd2aa5ca9d2460`, self-notes:
  "the CI contract test never caught it because it only checks data.js-vs-manifest identity,
  not resolution"); reflection `d682b2c6226bd9`; commit `77eb6c0b3`.

### F-06 — `git add -A` re-tracked 32,311 files before the `.gitignore` landed
- **Date:** 2026-09-08 23:23:36 (local).
- **ID:** `ses_f95ece514ffe…`.
- **What happened.** During stage-2 of the corpus migration the command chained
  `git add -A experiments/results` *before* appending the `experiments/results/` ignore
  rule in the same shell invocation, re-adding all 32,311 dirty tracked files to the
  index. The session caught it ~20 s later ("That was a mistake — I wanted to prevent
  re-adding, but -A re-added everything non-ignored."), ran a second
  `git rm -r --cached experiments/results`, and committed `ab887b5c8`
  (32,312 files, +6 / −15,620,993).
- **What should have happened.** Land the `.gitignore` change *first*, then remove cached
  paths, then add — never `add -A` in the same breath as the ignore that is meant to
  exclude the tree. (The session's own recorded lesson: "never git add -A before the
  .gitignore lands (it re-tracks everything)".)
- **Damage / cleanup cost.** A second full `rm --cached` over ~32k paths and a ~15 min
  window (the first attempt at 23:16:52 had timed out); near-miss of a giant re-add commit.
  Stage-1 (`292c47bad`, 23:14) had also committed 6 run ledgers into the tree that stage-2
  untracked 13 min later.
- **Severity:** 3 (near-miss; no bad commit landed — caught pre-commit).
- **Evidence pointers.** `opencode.db ses_f95ece514ffe… part@2026-09-08 23:23:36`
  (the chained command), `part@2026-09-08 23:23:55` ("That was a mistake"),
  `part@2026-09-08 23:24:11` (second `rm --cached`), `part@2026-09-08 23:27:57` (commit).
  Corroboration: `git show --stat ab887b5c8` (32,312 files, −15,620,993); stage-1
  `292c47bad`; reflection `6feb14bfb195be`.

### F-07 — opencode snapshot indexing froze the web UI until `snapshot:false`
- **Date:** sustained through 09-08 23:14 (fix), session interrupted to 09-09 05:07.
- **ID:** `ses_f95ece514ffe…`.
- **What happened.** opencode's per-turn snapshot git-indexed the whole working tree; the
  repo carried a **1.6 GB tracked results tree** (2.5 GB snapshot store), so every turn
  blocked the web server. The controller experienced repeated freezes ("you froze again.
  can we increase the web server resources or something?" 17:26:36; "stop fucking runnin
  this!!!!! it's hanging" 23:02:49). Root cause found 23:03–23:08 (docs quote: "large
  repositories… slow indexing and significant disk usage"), fixed with `"snapshot": false`
  in `~/.config/opencode/opencode.jsonc`; the web-unit restart at 09-09 01:19 interrupted
  the session until 05:07.
- **What should have happened.** The freeze was a known opencode failure mode; the tracked
  1.6 GB data plane should have been migrated out of git earlier (the migration is what
  permanently fixes it), and heavy foreground pipeline runs should have been avoided while
  diagnosing a UI freeze.
- **Damage / cleanup cost.** Days of degraded operator experience; several sessions lost to
  freezes; a web restart that cost hours of session continuity.
- **Severity:** 3.
- **Evidence pointers.** `opencode.db ses_f95ece514ffe… part@2026-09-08 17:26:36`
  (freeze report), `part@2026-09-08 23:02:49`, `part@2026-09-08 23:04:06` / `23:07:35`
  (1.7 GB, 32,305 tracked files), `part@2026-09-08 23:14:15` (edit `snapshot: false`),
  `part@2026-09-09 01:19:30` (web restart). Decision `14f69fd89590b7`
  (`decision:90834c33346dac1f`, category `ops`).

### F-08 — Phantom self-test emitter: 3 double-registered findings, never identified
- **Date:** registrations 2026-09-08 21:45:27Z; hunt 23:45 → 09-09 01:11.
- **ID:** `ses_f95ece514ffe…`.
- **What happened.** Three `self-test_*` `phase-finding/v1` rows were registered as a
  double row + artifact with no corresponding stream event. The session hunted across
  opencode sessions, host journald, systemd timers/crontab, docker containers, and the
  kb-worker reconcile code, then concluded: *"the emitter is not any opencode session,
  host process, container, or timer"*. The rows were tombstoned; root cause unknown. The
  close carried it as an open thread.
- **What should have happened.** Every registry write should be attributable to a producer
  path; the honest fallback after an exhaustive trace is what happened (tombstone + record
  the mystery), but a broken `observed_at`/`content_hash` artifact should have been
  detectable at write time (write-time validation), which would have made the emitter
  findable.
- **Damage / cleanup cost.** ~1.3 h of in-slice tracing (plus a re-hunt) and a permanent
  open question; 3 rows cleaned.
- **Severity:** 3.
- **Evidence pointers.** `opencode.db ses_f95ece514ffe… part@2026-09-08 23:54:27`
  (double row), `part@2026-09-09 01:11:26` (give-up text), `part@2026-09-09 00:53:35`
  (close open-thread). Close artifact `c44a102c09e4cdba` /
  `session:2026-09-08-aio-publication-closure` (kb `80fd2aa5ca9d2460`).

### F-09 — Recording-discipline gap: acts unrecorded until backfilled
- **Date:** 09-04 (27 permanence + kb-facts backfill) and 09-09 → 09-10 01:01 (6 acts).
- **ID:** AIO record layer (`decision_record.py`, `session_close.py`).
- **What happened.** The decision-recording machinery was live from ~09-04 but held
  **zero** records; 27 permanence decisions (08-30 → 09-04) had to be backfilled, and the
  kb-facts close cited a decision record (`80f02d3ce5`) that did not yet exist — the
  "close-record phantom". On 09-09 the audit repeated: "NOT recorded (no decision records):
  corpus migration, 402-row tombstone disposition, CI fixture strategy, backup
  architecture choice, session spine fix, snapshot:false, and tonight's six-item closure";
  six decisions were backfilled with `decided_at` 09-09 23:01 and the 09-09 close written
  at 01:01. The AIO's own rule: *"every consequential act gets its decision record at the
  moment of the act, not in the retrospective."*
- **What should have happened.** Emit the decision at decision time (the rail exists);
  never cite a record that is not on disk.
- **Damage / cleanup cost.** Two backfill campaigns; the record layer's `decided_at`
  values are partly reconstructions, not first-hand; one close shipped a phantom citation.
- **Severity:** 3.
- **Evidence pointers.** Decision artifacts `80f02d3ce520aa` (kb-facts merge; the phantom
  `80f02d3ce5`), the six `aio` decisions with `decided_at` `2026-09-09T23:01:2x–3xZ`
  (`5a53d9c107485b`, `f608523157d1c7`, `b720a850d12f37`, `29c2e52689b2a4`, `14f69fd89590b7`,
  `2f00e3a820268e`); close `session:2026-09-09-aio-stabilization-closure`
  (kb `62ae9536cfd933a7`, self-notes) + reflection `5043022b9db10e`; close
  `session:2026-09-04-aio-graph-leg-closeout` ("the close-record phantom 80f02d3ce5");
  transcript `part@2026-09-10 01:00:39` / `01:01:11` (audit admission), `01:01:25` /
  `01:01:35` (backfill), `01:01:45` (close).

### F-10 — Session-spine `close_seq` regression: `session open` read the wrong close
- **Date:** surfaced 2026-09-08; fixed 2026-09-09 16:07.
- **ID:** session spine (`session_ingestion.open_session`).
- **What happened.** Same-day closes were ordered by a slug-lexicographic tiebreak, so the
  09-08 `session open` retrieved the *morning* close record instead of the afternoon's —
  i.e. the session's opening posterior was the wrong (stale) record. `1eaf5914f` replaced
  the tiebreak with a content-stamped `close_seq`, preserving the rerun-safe re-close no-op.
- **What should have happened.** Order same-day closes by close order, keyed by content,
  not by slug. (The self-knowledge layer's own contract: session open retrieves the LAST
  close.)
- **Damage / cleanup cost.** One session (or more) opened against the wrong posterior; the
  fix plus a regression test cost the 09-09 tail.
- **Severity:** 3.
- **Evidence pointers.** Commit `1eaf5914f` (subject names "the 2026-09-08 open_session
  regression"); decision `2f00e3a820268e` (`decision:1f742d3977ea8a37`, category `spine`).

### F-11 — Stale control rows: promote did not close its own rows
- **Date:** 09-04 14:16 (mass close-out) and 15:32 (stale cancel); root fix same day.
- **ID:** control-db `run-f822d6ecd88b`, `run-426ca19fe025`, `run-17cc8e4e1e01`, plus 9 runs.
- **What happened.** `promote.py` merged content but never moved its control row out of
  `promotable`, leaving stale promotable rows for work already on `main` (`3e40537e2`,
  `9e4773fb1`). Two stale rows were cancelled and nine 09-03 merged rows were stamped
  `merged→projecting→published` retroactively at 09-04 14:16 by `controller-close-out`.
  The `promote_row_closeout` wave then fixed the root cause (close row on success + refuse
  stale tree-identical candidates). Three stale promotable rows were cancelled rather than
  promoted (graph_leg ×2 at 09-04T14:16, promote_row ×1 at 15:32) — none was an unclosed
  promotion.
- **What should have happened.** A promote that merges must close its own row
  (`promotable→merged`), so the control packet never advertises already-merged work.
- **Damage / cleanup cost.** A manual close-out sweep; hand-stamped terminal states that
  are reconstructions, not live transitions; an operator (and the packet) briefly shown
  stale promotable candidates. Corollary anomalies: the `approvals` table is **empty**
  (controller-signed merges/cancels left no approval rows) and the 9 retroactively
  "published" runs have **zero** publication receipts/deployments.
- **Severity:** 3.
- **Evidence pointers.** Control-db `run_transitions` ids 71, 72, 93, 94, 95 and the
  09-04T14:16:30 `merged→projecting→published` trio on 9 runs (see p2 file
  `control_db.md`); decision `bf513933c2d0e9` (`decision:438fb06d80fdebc2`, category
  `bookkeeping`); reflection `b69bed52834710`; commit `4d34e542b` / merge `9e4773fb1`.

### F-12 — Two workflow launches raced their worktree: `running` zombie rows
- **Date:** 2026-09-09 23:45:37 and 23:46:50 → closed 09-10 00:09:07 (UTC).
- **ID:** `run-d713e0c61620`, `run-2a19746f4106` (`recording_sweep`).
- **What happened.** Two `systemd-run` spec launches ran before the worktree existed
  (`workdir not found`); the runner creates the control row *before* validating the workdir,
  so both rows sat `running` ~23 min with no phases, $0, and zero step_attempts, until a
  `controller-close-out` reconciled them to `failed` ("crash residue: launched before the
  worktree existed"). The third attempt (`run-90a52204fb6c`) ran 3 phases and is the
  survivor.
- **What should have happened.** Validate the workdir before minting the run row (or create
  the row only after admission); a failed launch should be `failed`, not `running`.
- **Damage / cleanup cost.** Two zombie rows and a manual reconciliation; part of the
  trigger for the launch-path improvisation (F-13).
- **Severity:** 2.
- **Evidence pointers.** Control-db `run_transitions` ids 96–101; `control_meta` epoch
  308; see `control_db.md` §1/§3.

### F-13 — Launch-path improvisation: hand-rolled launcher written then deleted
- **Date:** 2026-09-10 02:10:50 (written) → 02:11:46 (deleted).
- **ID:** `ses_f95ece514ffe…`.
- **What happened.** After the two zombie launches (F-12) the session wrote
  `scripts/launch_workflow.py` (own worktree lifecycle + zombie guard) rather than using the
  existing `run_clone.py`/orchestrator path; the controller pushed back ("woah!!!!!!! are
  you on the right track? i dont think that is right."), and the session deleted it:
  *"I was inventing a third launcher when the machinery already owns this."*
- **What should have happened.** When the documented path fails, stop and use/repair the
  existing machinery; do not build a parallel mechanism.
- **Damage / cleanup cost.** A short detour and one deleted draft; the real fix was to use
  the existing launcher correctly.
- **Severity:** 2.
- **Evidence pointers.** `opencode.db ses_f95ece514ffe… part@2026-09-10 02:10:50`
  (write), `part@2026-09-10 02:11:34` (controller alarm), `part@2026-09-10 02:11:46`
  (delete).

### F-14 — Spec-wrapper over-delivery around a zero-model engine
- **Date:** 2026-09-10 01:22 → 01:27.
- **ID:** `ses_f95ece514ffe…`; commit `f7d9ebe42`.
- **What happened.** The deterministic, zero-model `scripts/recording_sweep.py` was wrapped
  in an agent-task spec (`workflows/repository/recording_sweep.yaml`, model-run phases
  `p0_scan`/`p1_backfill`/`p2_report`), plus Control Room routes and a nightly timer, and
  committed as the "recording rail". The AIO's retrospective admission: *"when the ask was
  ambiguous on shape, I built the bigger thing instead of asking; when machinery existed, I
  invented parallel machinery."* The wrapper's own phase runs are exactly the F-12 zombies.
- **What should have happened.** A deterministic engine needs a CLI/timer, not agent
  phases; the extra wrapper added surfaces (spec, routes, timer) and two failed runs.
- **Damage / cleanup cost.** Extra surface (commit + portal routes + timer) and the F-12
  zombie runs; the controller had sanctioned "all 3", so the in-moment read was ambiguous —
  the over-delivery is the retrospective verdict.
- **Severity:** 2.
- **Evidence pointers.** `opencode.db ses_f95ece514ffe… part@2026-09-10 01:22:00`,
  `part@2026-09-10 01:23:20` (write spec), `part@2026-09-10 01:25:02` (routes),
  `part@2026-09-10 01:26:24` (timer), `part@2026-09-10 01:27:23` (commit), and
  `part@2026-09-10 02:13:57` ("Own it…"). Commit `f7d9ebe42`.

### F-15 — Wrong-script / wrong-selection runs corrected mid-flight
- **Date:** 09-08 16:25 → 23:41; also hammer-internal.
- **ID:** `ses_f95ece514ffe…`, `ses_f92f8804affe…`.
- **What happened.** Multiple runs were started with the wrong tool or selection and
  corrected: a kb-artifact audit with a future mtime filter (found "nothing", 16:25:29 →
  corrected 16:25:45); `rg` assumed on PATH (16:30:20); a foreground `pytest tests/ -q -x`
  full-suite run at 23:28 (UI froze; self-correction 23:41:28: "Running the full local suite
  was my mistake — it's hours + live tests by design", re-run under a systemd unit); and
  repeated foreground heavy pipeline runs while the UI was already frozen ("stop fucking
  runnin this!!!!!", 23:02:49). The recovered hammer trail likewise re-ran the lab/regen
  chain twice.
- **What should have happened.** Use the documented runner selection (`pytest -m 'not
  external'`, systemd units for long runs; the correct tools/commands) — the repo documents
  both. (This is the "wrong script / wrong command shape" class, distinct from F-13's
  building-a-new-mechanism.)
- **Damage / cleanup cost.** Wasted compute/time and operator friction; several UI freezes;
  no lasting damage.
- **Severity:** 2.
- **Evidence pointers.** `ses_f95ece514ffe… part@2026-09-08 16:25:29` / `16:25:45`,
  `16:30:20`, `23:02:49`, `23:03:02`, `23:28:15`, `23:41:28`; hammer trail
  `ses_f92f8804affe… part@2026-09-05 03:00` (second regen).

### F-16 — Large operations performed directly on `main` (permanence bypass)
- **Date:** whole window.
- **ID:** author line commits on `main` (`instrument`).
- **What happened.** All of the window's heavy data/permanence work — the stabilization
  wave `bb47441bc`, both migration stages `292c47bad`/`ab887b5c8`, the publication snapshot
  `77eb6c0b3`, the drain merge `9e4773fb1` — was committed directly on the `main` checkout
  and pushed, bypassing the worktree/promote split. The 09-09 close records the live gap:
  *"permanence split (promoter service / AIO break-glass) — the demonstrated live gap
  (branch protection bypassed via enforce_admins:false)"*. Two sessions also shared the one
  main checkout concurrently on 09-04, fighting over refs. The correct shape (a feature
  worktree) was adopted only for the postmortem wave at 09-10 02:14:48.
- **What should have happened.** The permanence gate is controller-only and work rides
  ephemeral branches; machine-state sweeps are legitimate on `main` only for small derived
  surfaces, not a 1.6 GB data plane or a merge of an append-only log. The concurrent-session
  hazard violates the single-writer rule.
- **Damage / cleanup cost.** This is the structural precondition for F-01 (dirty main
  checkout), F-03 (drain merge), and F-07 (snapshot freeze); the migration was the eventual
  correction.
- **Severity:** 3 (systemic; each individual consequence is scored separately).
- **Evidence pointers.** Commits `bb47441bc`, `292c47bad`, `ab887b5c8`, `77eb6c0b3`,
  `9e4773fb1`; close `session:2026-09-09-aio-stabilization-closure`
  (kb `62ae9536cfd933a7`, open-thread text); reflection `b69bed52834710` ("A concurrently-
  running session probing the same checkout destabilizes refs"); transcript
  `part@2026-09-10 02:14:48` (worktree add) and `part@2026-09-10 02:13:57` ("Own it").

### F-17 — Data-plane container with no provenance contract shadowed the live corpus
- **Date:** root cause pre-window (container created 08-31); root-caused + repaired 2026-09-04.
- **ID:** `kb-neo4j` container / chromadb; session `2026-09-04-kb-facts-and-graph-repair`.
- **What happened.** `infrastructure_kb-neo4j_1` was created with
  `FINOPS_REPO_DIR=/tmp/wt_fleet_submit`, whose `experiments/results` overlay shadowed the
  live corpus → **9,121 `FileNotFoundError` dead letters** from Aug 24 through 09-04,
  including F2 gen2 records and session closes (silent projection failure for ~2 weeks).
  Chromadb on :8100 was an ad-hoc container, never volume-backed; recreating it lost the
  dense index, which had to be rebuilt from the stream. The AIO root-caused, restored the
  service against the live corpus, surgically replayed 4,490 hash-verified events, and
  confirmed retrieval's lexical leg.
- **What should have happened.** A data-plane store with a persistence + mount contract;
  containers that read the corpus must be validated against the live root, and projection
  silence must be distinguishable from health (the watermarks exist for this).
- **Damage / cleanup cost.** ~2 weeks of silent dead-lettering; a surgical replay of 4,490
  events + a chroma rebuild (resilience claim proven, but at real cost); removal of a
  mistaken systemd unit.
- **Severity:** 4 (silent data-plane degradation, recovered).
- **Evidence pointers.** Close `session:2026-09-04-kb-facts-and-graph-repair`
  (kb `0bd5105085aa7fd0`, self-notes) + reflection `89492bfb69e749`; close
  `session:2026-09-04-aio-graph-leg-closeout` (kb `8bade3f3986819db`, self-notes: broken-
  pointer class, 2,184 hash-verified republishes; chromadb wedge).

### F-18 — Idle-exit footgun + ghost heartbeats
- **Date:** discovered 2026-09-04.
- **ID:** `kb_worker`; heartbeat registry.
- **What happened.** `kb_worker.py` exited 0 after 12 empty polls, so a healthy, caught-up
  daemon (under compose `restart:on-failure`) was left **DEAD**; and ~703 ghost
  analysis-worker heartbeat keys had no TTL (minted by `--once` processes). The session
  applied a runtime restart policy for the daemon and a TTL on `publish`, swept the stale
  keys (unhealthy workers 0), and the code fixes + tests landed in `3e40537e2`.
- **What should have happened.** A long-running consumer should idle, not exit (idle-exit
  only under `--once`); heartbeat keys carry a TTL. Both are now fixed.
- **Damage / cleanup cost.** A dead-but-healthy daemon and 703 stale health keys misled
  health surfaces until swept; small.
- **Severity:** 2.
- **Evidence pointers.** Close `session:2026-09-04-kb-facts-and-graph-repair`
  (kb `0bd5105085aa7fd0`, open-thread "kb_worker idle-exit footgun");
  close `session:2026-09-04-aio-promote-row-closeout` (kb `8bd15a0076a59afe`,
  "703 ghost analysis-worker heartbeats"); commit `3e40537e2`.

### F-19 — Generated-surface drift: spec index regenerated, README count not synced
- **Date:** 2026-09-10 01:27 (rail commit) → 01:56 (index refresh), local.
- **ID:** commits `f7d9ebe42` + `24837b7d0` (recording rail).
- **What happened.** The recording-rail commit chain added `recording_sweep` and
  regenerated the derived spec index (`experiments/specs/index.json` / `STATUS.md`, commit
  `24837b7d0`: 66 lines changed) to 192 specs (11 experiments + 181 workflows), but the
  README spec-count row was left at `191 (11 experiments + 180 workflows)`. The doc-lifecycle
  lint (`tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index`) fails on the
  branch HEAD. (A second instance of the same class: the `aio_controller_postmortem` spec
  `e3bf2a45e` is not yet in the index at all.)
- **What should have happened.** The generated-surface rule: when a derived surface
  regenerates, resync its dependents in the same wave ("regenerate spec_status from the
  checkout root where the gate runs, then sync README"). This is the recurring drift the
  09-04 reflection already named.
- **Damage / cleanup cost.** A red gate that must be cleared before the wave's test gate;
  trivial mechanical fix once known.
- **Severity:** 2.
- **Evidence pointers.** Commits `f7d9ebe42`, `24837b7d0`, `e3bf2a45e`;
  `experiments/specs/index.json` (spec count 192; `recording_sweep` present,
  `aio_controller_postmortem` absent) vs `README.md:96` ("191 (11 experiments + 180
  workflows)"); test output
  `tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index` FAILED.

---

## 4. Unverified / excluded

**None.** Every candidate item harvested from the six surfaces above was traceable to at
least one first-hand pointer. Two items were deliberately *not* elevated to corpus entries
because they are correct behavior, not failures:

- The hammer's P0 promote decision (09-04 17:30): `workflow promote` was **correctly
  refused** as stale/tree-identical and the run row cancelled via the transition API — a
  defense working as designed (`ses_f92f8804affe… part@2026-09-04 17:32:36`).
- The `g10_test_gate` failures (`run-57b8ec179e30` deprecation-warning-fatal, $0.54;
  `run-e33f4a5eeb66` syntax error, $3.32): expensive, but the gate catching a real defect is
  the gate working. Recorded here as context for F-11/F-12, not as AIO failures.

An item was also excluded as out-of-scope-by-date: the web-UI freeze's *inception*
(pre-window), retained only as the in-window fix F-07; and the container provenance
defect F-17, whose repair is in-window but whose root cause pre-dates 09-04.

---

## 5. Recording-sweep audit (surface f) — as-evidence

The rail (`scripts/recording_sweep.py`, commit `f7d9ebe42`) scans commit-days against the
decision/close artifacts and can backfill uncovered days with reconstructed rationale
(actor `recording-sweep`), plus a phantom-close-claim detector (a close citing a
`decision record <id>` with no artifact — the F-09 class).

- **Committed audit** `experiments/results/recording/audit.json`, generated
  `2026-09-10T01:26:05`: `window_days=14`, `commit_days=11`, `decided_days=10`,
  `closed_days=3`, `gap_days=[]`, `phantom_close_claims=[]`.
- **Live re-scan at mining time** (`2026-09-10T02:33:14`): `commit_days=12`,
  `decided_days=10`, `closed_days=3`, `gap_days=["2026-09-10"]` (today's commits are not yet
  covered because this postmortem session has not closed), `phantom_close_claims=[]`.
- The three `recording-sweep` day backfills (`decision/v1`, actor `recording-sweep`,
  category `recording`): `10562e7c46627f` (08-27), `230d032547dbfc` (08-28),
  `c451edb3887630` (08-29) — each `why` begins "day had main commits but no decision record
  and no session close", i.e. the rail closes exactly the F-09 class for pre-AIO days.
- The rail's own runs are the F-12 zombie residue (`run-d713e0c61620`,
  `run-2a19746f4106`) plus the survivor `run-90a52204fb6c` (3 phases, now `promotable`).

**Reading:** the audit's post-backfill clean state is the *remediation working*, not
evidence the gap did not exist. The gap is attested by the 09-09 discipline audit
(F-09: six acts unrecorded until backfilled) and by the rail's own existence.

---

## 6. p0 completion log

- **GATE — ≥ 12 items:** PASS (19 items, F-01…F-19).
- **GATE — every item carries an evidence pointer:** PASS (each item lists `part@`
  timestamps / KB artifact stems / decision ids / control rows / commit shas / the audit
  file). Zero items marked unverified; none excluded.
- **GATE — surfaces (a)–(f) each mined:** PASS. (a) 9 closes + 9 reflections; (b) 42
  decisions incl. the 3 `recording-sweep` backfills and the 6 backfilled AIO acts; (c)
  control-db runs/transitions/step_attempts/outbox/approvals; (d) main + all-refs commit
  shapes, reflog (one aborted-rebase correction), stash list, the fix-a-commit arcs; (e)
  hammer reconstruction + the 09-08/09-09 author-line slice; (f) the recording-sweep audit
  (committed + live) and the rail's semantics.
- **LOG:** PASS.
