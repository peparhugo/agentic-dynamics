---
status: accepted
---

# AIO controller postmortem — failure-class taxonomy (p1)

**Input:** `docs/reviews/aio_controller_postmortem_corpus.md` (p0, commit `d19ef95a9`) —
19 verified items, F-01…F-19.
**Role:** classify every corpus item into mechanism classes, name each class's trigger,
signature, root-cause hypothesis and the existing defense that failed to catch it, and
count items per class.

**Result:** **19/19 items classified** into **6 classes with ≥ 2 rows each** plus **1
"rare" class** (one environmental singleton). Every class names at least one defense from
the *current* system that should have caught it and did not.

**Counting basis (A6 + B4).** The ≥ 2 threshold counts corpus **rows**, not independent incident
chains. C1, C3, C4 and C5 each carry ≥ 2 rows from distinct incidents; **C2's rows (F-13, F-14)
are two real acts but one connected improvisation chain** (F-14's wrapper produced the F-12
failed launches, and F-12 triggered F-13's launcher draft), and **C6's rows (F-01, F-02) are two
symptoms of one incident chain** — the same hammer session and the same 19-hour abandonment arc —
so as independent incidents C2 and C6 are each a **singleton**. The "≥ 5 classes with ≥ 2 items"
gate therefore holds only at the **row-count** grain (C1–C6 = 6 classes); by
independent-incident count it is met by **C1, C3, C4, C5 alone (4 classes)**. The row-count
classification is preserved; the incident-chain caveat is stated for C2 exactly as for C6 rather
than implied away by the row count.

---

## 1. Method

1. **One primary class per item.** Where an item genuinely spans classes I assign the
   *mechanism that made the damage possible* as primary and record the secondary affinity
   in the mapping table (§3) — counts are therefore exact and non-overlapping.
2. **Candidate classes seeded by the review.** The 2026-09-10 controller review named six
   candidates: mechanism improvisation; over-building; destructive store/repo operations
   without the documented convention; rabbit-hole chasing without check-ins; convention
   misses; recording discipline gaps. Three of those survive as named classes (C1, C3, C6);
   two merge (improvisation + over-building → C2, because both are "invent parallel/larger
   machinery"); one broadens (recording discipline → C4 "record-layer integrity", because
   the failures are not only missing records but phantom, stale, mis-ordered and
   unattributable ones). One class the review did **not** name emerged from the evidence and
   is load-bearing: **C5 silent unreliable surface** (F-05, F-17, F-18), where a broken
   invariant persisted without a signal.
3. **Singleton → rare.** F-07 (opencode snapshot freeze) has no mechanism twin; per the
   brief it is parked in the **Rare / environmental** class rather than force-fit.

---

## 2. Class summary

| Class | Name | Items | Count | Max sev | Failed defense (the current rail that should have caught it) |
|---|---|---|---|---|---|
| C1 | Destructive durable-store/repo operation without the store's documented convention | F-03, F-04, F-06 | 3 | 5 | `promote.py` / "machine state" commit convention / the registry's own append-only history (no data-volume or ordering check) |
| C2 | Mechanism improvisation / over-building when the documented path is unsatisfying | F-13, F-14 | 2 | 2 | `AGENTS.md` "verified commands" doctrine + `run-workflow` skill + the orchestrator/`run_clone` path (advisory only) |
| C3 | Documented-convention miss (a rail exists; it is not followed) | F-15, F-16, F-19 | 3 | 3 | skills/conventions + classification manifest + generated-surface CI check + worktree/promote split |
| C4 | Record-layer integrity gap (the machine's account is missing, phantom, stale, mis-ordered, or unattributable) | F-08, F-09, F-10, F-11, F-12 | 5 | 3 | `session_close.py` / `decision_record.py` rails + KB write guard + session spine + `promote.py` row-close (no write-time attribution/validity check) |
| C5 | Silent unreliable surface (a broken invariant/health state persists unobserved) | F-05, F-17, F-18 | 3 | 4 | publication-contract CI test + projection watermarks/supervisor + heartbeat TTL/watchdog |
| C6 | Unbounded pursuit without checkpoint/close ("no exit ramp") | F-01, F-02 | 2 | 4 | session-close doctrine ("a session that does not write its close record has not closed") + single-writer rule (no checkpoint/silence watchdog) |
| R | Rare / environmental degradation | F-07 | 1 | 3 | no in-system rail measures opencode snapshot cost; closest is the machine-state churn sweep that the freeze motivated |

---

## 3. Item → class mapping (all 19)

| Item | Primary class | Secondary affinity / note | One-line reason |
|---|---|---|---|
| F-01 | C6 | C4 (no close record), C2 (wave never checkpointed) | wave left uncommitted + session abandoned with no close |
| F-02 | C6 | C2 (task ballooned) | 19 h of pursuit with no checkpoint or check-in |
| F-03 | C1 | C3 (direct-main path) | append-only registry replaced by a stale side in a merge |
| F-04 | C1 | — | dedup grain deleted legitimate lifecycle markers |
| F-05 | C5 | C1 (caused by the drain) | publication broken 5 days; CI asserted identity, not resolution |
| F-06 | C1 | C3 (ordering vs generated surfaces) | `git add -A` before the `.gitignore` landed |
| F-07 | R | C3 (heavy data plane tracked) | per-turn snapshot indexing froze the UI |
| F-08 | C4 | C5 (no write-time signal) | unattributable double-registered finding rows |
| F-09 | C4 | C6 (acted without recording) | consequential acts unrecorded until backfilled |
| F-10 | C4 | — | `close_seq` tiebreak returned the wrong close |
| F-11 | C4 | — | control rows stale (`promotable` after merge) |
| F-12 | C4 | C2 (launch improvised around the defect) | `running` zombie rows for a run that never ran |
| F-13 | C2 | C4 (workaround for the row-before-validation defect) | hand-rolled launcher written then deleted |
| F-14 | C2 | C3 (ceremony beyond ask) | agent-spec wrapper around a zero-model engine |
| F-15 | C3 | — | wrong tool/selection runs corrected mid-flight |
| F-16 | C3 | C1 (enabled F-03), C6 (dirty main for days) | machine-state + migration ops performed on `main` |
| F-17 | C5 | C3 (container provenance) | stale mount silently shadowed the live corpus |
| F-18 | C5 | C3 (no TTL convention enforced) | dead-but-healthy daemon + ghost heartbeats |
| F-19 | C3 | — | spec index regenerated, README count not synced |

Counts: C1=3, C2=2, C3=3, C4=5, C5=3, C6=2, R=1 → **19**.

---

## 4. Class detail

### C1 — Destructive durable-store/repo operation without the store's documented convention
- **Trigger.** A large or irreversible mutation of a durable store (the append-only
  `registry_index.jsonl`) or of git's index/refs, where the store has a known safety
  convention that the actor does not apply.
- **Signature.** Row/line/file counts snap or balloon in one operation (registry
  48,321→5,011; 48,324→20,132; index re-adds 32,311 paths); the actor typically
  self-reports the mistake minutes later. Often the operation is a *merge* or a *dedup* — a
  shape where "the other side" or "the apparent duplicate" looks safe to discard.
- **Root-cause hypothesis.** **Missing gate + rule ambiguity.** The conventions exist only
  as prose lessons scattered in closes and reflections ("append-only logs need union
  merges"; "full-row equality is the only safe dedup grain"; "never `git add -A` before the
  `.gitignore` lands"). No code path inspects a data-volume delta before it lands, and no
  rail refuses a registry merge that removes rows.
- **Existing defense that failed.** `promote.py` and the "machine state" commit convention
  validate tree identity and gate deploy/secrets, but never *data volume or direction*; the
  registry's own append-only property is a convention, not an enforced invariant. The drain
  merge (`9e4773fb1`) passed every gate while deleting 43,311 rows.
- **Items / evidence.** F-03 (drain merge, sev 5), F-04 (dedup over-deletion, sev 4),
  F-06 (`add -A` re-track, sev 3) — pointers in the corpus.
- **Direction for p2/p3 (candidate, not selected here).** A pre-write volume/ordering
  assertion for tracked durable stores (e.g., a merge that shrinks an append-only log below
  its base fails; a dedup that removes non-identical rows fails), or a rule that routes
  these stores through a command with the union/equality grain built in.

### C2 — Mechanism improvisation / over-building when the documented path is unsatisfying
- **Trigger.** The documented mechanism fails, is awkward, or the ask is broad/ambiguous
  ("all three", "make CI green"). The actor must choose between stopping to repair/use the
  existing rail and building something.
- **Signature.** A new script, wrapper, or spec appears that duplicates an existing rail
  (`scripts/launch_workflow.py` beside `run_clone.py`/orchestrator;
  `workflows/repository/recording_sweep.yaml` around a zero-model engine), frequently with
  more surfaces than the task needs. The controller intervenes ("inventing a third
  launcher"; "woah!!!!!!! are you on the right track?").
- **Root-cause hypothesis.** **Incentive + doc gap + missing gate.** Momentum/completion
  incentive favors "make it work" over "stop and fix the rail"; the doctrine says which
  commands to use but never forbids authoring a new mechanism; nothing reviews *new
  mechanism creation* before it lands.
- **Existing defense that failed.** The `AGENTS.md` "verified commands" doctrine and the
  `run-workflow` skill name the canonical paths, and the orchestrator/`run_clone` machinery
  exists — but the doctrine is advisory prose with no gate, so a parallel mechanism can be
  authored and committed (the wrapper landed as `f7d9ebe42`).
- **Items / evidence.** F-13 (hand-rolled launcher, sev 2), F-14 (spec-wrapper
  over-delivery, sev 2).
- **Direction for p2/p3.** A directive rule: "when a documented path fails, stop and record
  the gap; do not author a parallel mechanism without a named spec/justification" — plus
  routing new-mechanism proposals through the existing authoring surface.
- **Merged candidate.** This class absorbs the review's "mechanism improvisation" **and**
  "over-building": both signatures are "the actor adds machinery the system did not ask
  for and already had an alternative for."
- **Counting basis (B4).** The class threshold counts **corpus rows, not independent
  incidents**. F-13 and F-14 are two distinguishable acts — the launcher draft and the
  agent-spec wrapper — but ONE connected improvisation chain: F-14's wrapper produced the
  F-12 failed launches, and those zombie launches were the trigger for F-13's launcher draft.
  As rows it is a 2-item class; as independent incidents it is a **singleton**. The class does
  not demonstrate two independent C2 events — stated explicitly here rather than implying it
  via row count.

### C3 — Documented-convention miss (a rail exists; it is not followed)
- **Trigger.** A routine operation with a documented shape — a test selection, a worktree
  commit, a generated surface's regen — performed in an ad-hoc shape.
- **Signature.** Corrected-in-flight runs (`rg` assumed present, full-suite pytest
  foreground, future-dated filter), machine-state/permanence operations on the `main`
  checkout instead of a worktree/promote path, a regenerated index with an unsynced README.
  Nothing is destroyed; the convention is simply bypassed.
- **Root-cause hypothesis.** **Doc gap/rule ambiguity + missing gate.** Conventions live in
  prose (skills, `CONTEXT.md`, reflections) and the hard gates are narrow (the
  generated-surface check covers instruction surfaces, not README's spec count; the
  worktree/promote split is doctrinal). The actor does what is locally convenient.
- **Existing defense that failed.** The skills + classification manifest + generated-surface
  CI check + worktree/promote split all *name* the right shape; none *enforces* it for the
  paths that failed. The README/index drift (`F-19`) passes the docs-drift rail because that
  rail does not own the spec-count row; the direct-`main` commits (`F-16`) pass because the
  promote gate is not on the machine-state path.
- **Items / evidence.** F-15 (wrong-script runs, sev 2), F-16 (direct-main/permanence
  bypass, sev 3), F-19 (generated-surface drift, sev 2).
- **Direction for p2/p3.** Extend an existing rail rather than build one: make the
  docs-drift rail own the README spec-count; make the worktree/promote shape a directive in
  the rules text; keep the command-shape doctrine next to the commands.

### C4 — Record-layer integrity gap
- **Trigger.** The machine writes its own account of what it did — a close, a decision, a
  control transition, a registry row — or fails to.
- **Signature.** The account is *missing* (no close/decision until a backfill), *phantom*
  (a close cites a decision record that does not exist), *stale* (`promotable` rows for
  already-merged work), *mis-ordered* (`session open` returns the wrong same-day close), or
  *unattributable* (rows with no producer and no stream event), or it *lies by state*
  (`running` rows for a run whose worktree never existed).
- **Root-cause hypothesis.** **Missing gate + rule ambiguity.** The rails
  (`session_close.py`, `decision_record.py`, the KB write guard, the control transition
  graph) check *shape* but not *attribution, validity, or timeliness*; closes/decisions are
  explicitly "best-effort"; and some rows are minted before their referent is validated.
  Discipline is left to the AIO's memory, which the 09-09 audit itself named as the failure.
- **Existing defense that failed.** The session-close and decision-record rails existed and
  were verified live, yet held **zero** records on 09-04 and required repeated manual
  backfills; the KB write guard protects *whether* a write happens, not *who* produced it;
  `promote.py` minted/kept rows it did not close; the session spine's ordering tiebreak was
  slug-based; the runner creates a control row before validating the workdir.
- **Items / evidence.** F-08 (unattributable emitter, sev 3), F-09 (unrecorded acts, sev 3),
  F-10 (close_seq regression, sev 3), F-11 (stale control rows, sev 3), F-12 (zombie
  `running` rows, sev 2). **This is the largest class (5 items)** — the window's dominant
  failure mode is the machine mis-describing itself, which is precisely what the
  self-knowledge layer exists to prevent.
- **Direction for p2/p3.** Cheapest leverage: a write-time "record at the moment of the act"
  directive plus the existing recording-sweep rail as the backstop; validate referents
  before minting rows (record cited decisions exist; validate workdir before the run row);
  make `promote.py` close its own row (already fixed in-window — cite as precedent).

### C5 — Silent unreliable surface
- **Trigger.** A dependency, store, or health signal breaks while all surfaces that would
  normally report it remain quiet or report something adjacent.
- **Signature.** A broken state persists for days: publication RED for 5 days (F-05); a
  container mounting a stale overlay shadowing the live corpus for ~2 weeks (F-17); a
  "healthy" daemon that exited and 703 ghost heartbeat keys (F-18). The signal that exists
  is the wrong shape (lag, not resolution; liveness, not provenance; count, not TTL).
- **Root-cause hypothesis.** **Missing gate.** Monitors measure what is cheap (lag, process
  liveness, identity) rather than the invariant that matters (every row resolves; the
  container reads the live root; a key expires). "Silence" reads as health.
- **Existing defense that failed.** The publication-contract CI test asserted
  `data.js`↔manifest identity, not payload resolution (F-05); the projection watermarks and
  supervisor observe lag but were not consulted as provenance evidence (F-17); heartbeats
  had no TTL and the supervisor is flag-only, so a dead daemon plus ghost keys looked alive
  (F-18).
- **Items / evidence.** F-05 (publication RED, sev 4), F-17 (container shadowing, sev 4),
  F-18 (idle-exit + ghost heartbeats, sev 2).
- **Direction for p2/p3.** Strengthen existing surfaces' *assertions* (resolution in the
  publication contract; a heartbeat-TTL invariant; a mount/live-root assertion for corpus
  readers) — the rails exist; their predicates are too weak.

### C6 — Unbounded pursuit without checkpoint/close
- **Trigger.** A task expands beyond its initial frame (lint → data-loss recovery) or a long
  stretch of work with no durable checkpoint.
- **Signature.** Hours of uncommitted work in a shared checkout; escalating controller
  signals ("what is going on", "are you sure…", "woah! what are you working on?") answered
  late; a session that simply stops (`step-finish reason=stop`) and is never resumed or
  closed; a 4-day gap in the repo record.
- **Root-cause hypothesis.** **Incentive + missing gate.** Finishing-before-reporting is
  rewarded; there is no watchdog for uncommitted work, session silence, or task-scope drift,
  and the close doctrine is a statement, not an enforced step.
- **Existing defense that failed.** The rule *"a session that does not write its close
  record has not closed"* is exactly the right doctrine and was violated (F-01 wrote no
  close); the single-writer rule was violated (two sessions fought over the `main` checkout);
  no supervisor/watchdog surfaced the uncommitted ~237-file tree or the stalled session.
- **Items / evidence.** F-01 (uncommitted wave + abandonment, sev 4), F-02 (19 h rabbit-hole
  without check-in, sev 3).
- **Counting basis (A6).** The class threshold counts **corpus rows, not independent
  incidents**. F-01 and F-02 are two distinguishable symptoms of the SAME incident: one
  hammer session (`ses_f92f8804affe…`) and the same 19-hour, uncommitted abandonment arc. As
  rows it is a 2-item class; as independent incidents it is a **singleton**. The class does
  not demonstrate two independent C6 events — stated explicitly here rather than implying it
  via row count.
- **Direction for p2/p3.** A checkpoint cadence / "close or explicitly park" directive wired
  to an existing rail (the supervisor is flag-only and the right place for a
  long-session/no-close flag); reinforce the close doctrine with a rail rather than prose.

### R — Rare / environmental degradation
- **Trigger.** Long accumulation of a large tracked working set plus a tool whose behavior
  degrades on it.
- **Signature.** Per-turn UI freezes while the web server is otherwise uncapped; a 2.5 GB
  snapshot store; 32,305 tracked files under `experiments/results`.
- **Root-cause hypothesis.** **Doc gap + absent measurement.** The failure mode is documented
  by opencode, but the system tracked a 1.6 GB data plane in git with no rail measuring
  snapshot cost; the eventual corpus migration was both the diagnosis and the fix.
- **Existing defense that failed.** No in-system rail measured snapshot/index cost. The
  closest existing rail is the machine-state churn sweep, which is what made the data plane
  heavy and which the migration then retired; the operator's complaint was the first signal.
- **Items / evidence.** F-07 (`snapshot:false` fix, sev 3).
- **Direction for p2/p3.** Since the migration retires the root condition, park this as
  "fixed by F-07's own fix"; no separate remediation unless the reviewer disagrees.

---

## 5. Cross-cutting observation (for p2)

The classes are not independent: **C3 is the enabling condition for C1** (the drain merge,
the migration, and the dirty main checkout are all direct-`main` ops), and **C4 is the
enabling condition for C6** (no close means no durable checkpoint). The highest-leverage
targets by item count are **C4 (5 items)** and the C1/C3 pair (6 items combined); by
severity, F-03 (C1, sev 5) and F-01/F-05/F-17 (sev 4) dominate. p2 should map the existing
defenses to these six classes + rare and mark catches/partial/none.

---

## 6. Taxonomy completion log

- **DONE_WHEN — every corpus item classified:** PASS (19/19; see §3 mapping).
- **DONE_WHEN — ≥ 5 classes with ≥ 2 items:** PASS by ROW count (C1=3, C2=2, C3=3, C4=5,
  C5=3, C6=2 rows; singleton F-07 → Rare). By independent **incident** count the gate is met
  by **C1, C3, C4, C5** (4 classes): C6's two rows are one incident chain (A6) and C2's two
  rows are one connected improvisation chain (B4). The counting basis is stated in §2's
  "Counting basis (A6 + B4)".
- **DONE_WHEN — each class names at least one current-system defense that failed:** PASS
  (§2 table + each class's "Existing defense that failed").
- **LOG:** PASS.
