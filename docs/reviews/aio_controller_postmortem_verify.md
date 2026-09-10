---
status: accepted
---

# AIO controller postmortem — replay verification (p5; revised under g10; claim-narrowed under the third review's F1–F4)

**Inputs:** the p4 branch (`61c4c97fe`), the p0 corpus (`d19ef95a9`), and the g9 adversarial
review (`docs/reviews/aio_controller_postmortem_adversarial.md`, `272ffaa89`).
**Role:** replay each selected remediation against the historical signature it targets and
record the outcome. A remediation that does not demonstrably refuse that signature is reverted
or re-designed here — never shipped unverified.

**Correction of the original p5 headline.** The first p5 doc claimed "4 of 5 pass as applied;
R1 was re-designed in this phase … All five are committed verified"
(`aio_controller_postmortem_verify.md`, original §Headline). The g9 adversarial falsified that
at the selected-remediation scope. This revision **retracts** the over-broad claims and
records the repaired, replayed state item by item (§0). No claim below rests on the
deleted headline.

**Second convergence pass.** A second adversarial re-review raised findings A5 and B1–B4
against the first repair. That revision dispositioned each in §0b: **A5** repaired with the
primary `git status` part; **B1 (P0)** repaired by adding a second guard at the same manifest
seam (§2b) — the false version-count "catches F-04" sentence was replaced; **B2** keeps R4 as
an explicit policy residual (removed from the catching-rail PASS); **B3** retains F-06's
re-track vector as a residual; **B4** states C2's counting basis exactly as C6's.

**Third pass (claim narrowing, F1–F4).** A third adversarial re-review (F1–F4 in the same
review doc) found the repair's *wording* still over-claimed. This pass renames and bounds the
B1 guard to what it is — a **raw-source-row-count drain guard** — including its equal-count
replacement limitation (§2b), and rewrites the release predicate to name only individually
exercised signatures: R1/F-09, R2/F-03 and the count-decrease form of F-04, R3/F-19, R5/F-05
(§10). F-01 remains a policy/detection residual, not a catch; F-04's equal-count replacement
form, F-15, F-16, F-17 and F-18 are explicitly not claimed. The release predicate below is now
true sentence by sentence.

> **Naming note (F1).** The p5 commit message (`96958a4d5`) calls the added rail a
> "full-row/lifecycle-marker conservation guard." That log line is historical and immutable;
> this pass supersedes it in the durable surface: the rail is a **raw-source-row-count drain
> guard**, bound in §2b, in `scripts/generate_manifest.py`'s docstrings, and in the final
> commit's release text. No full-row or content conservation is claimed anywhere.

**Environment note.** `experiments/results/**` is untracked runtime data and is absent from
this worktree, so replays use hermetic copies / detached worktrees where a data root would
otherwise be required. Every command below was run on this branch (HEAD after the g10 repair).

---

## 0. Disposition of the g9 findings (A1–A7) + the g10 gate

| Finding | Severity | Disposition in this phase | Replay evidence |
|---|---|---|---|
| **A1** R1 self-masks a same-day close | P0 | **REPAIRED** — coverage invariant re-designed; a close never covers its own day | §1a: e2e `test_same_day_close_cannot_cover_its_own_audit` (real `session close`) |
| **A2** R1 presented as C4, implements F-09/F-01 | P0 | **REPAIRED (scope reduced + marked)** — R1's scope is F-09/F-01; F-08/F-11/F-12 explicitly uncovered/attributed | §1b |
| **A3** R5 is an attestation, not a resolver replay | P0 | **REPAIRED** — real fixture-tier resolver replay added | §5: `test_fixture_tier_resolver_resolves_every_current_row_and_fails_on_one_unresolvable` |
| **A4** C1 severity-5 has no catching rail | P0 | **REPAIRED** — bounded drain guard on the active registry-compaction path | §2: `test_registry_drain_guard_refuses_a_smaller_compaction` + F-03 numeric proof |
| **A5** 292-file count unsupported | P1 | **REPAIRED** — now ~237 (1 modified + 236 untracked) with the exact retained `git status` part | §6a: `part@2026-09-04 17:26:48` |
| **A6** C6 class size inflated by row-splitting | P1 | **CORRECTED** — counting basis stated; C6 is a singleton incident | §6b |
| **A7** recording rail inconsistent with its own unmeasured claim | P1 | **REPAIRED** — `scan()` returns `unmeasured`; report/backfill refuse; source-checkout replay | §7 |
| **g10** fast path fails its gate | gate | **REPAIRED** — corpus-dependent modules de-`fast`-marked + audit hardened; fast path green at ~27s | §8 |

### 0b. Disposition of the second adversarial review (A5, B1–B4)

| Finding | Sev | Disposition in this pass | Replay evidence |
|---|---|---|---|
| **A5** dirty-file count has no primary pointer | P1 | **REPAIRED** — the retained `git status` part is now cited in F-01's evidence list | §6a: `part@2026-09-04 17:26:48` → 237 = 1 modified + 236 untracked |
| **B1** R2's F-04 coverage over-claimed | P0 | **REPAIRED (bounded in the F1 third pass)** — a raw-**source-row-count** drain guard added at the same `generate_manifest` seam (the false "catches F-04" sentence is replaced; it refuses only a count DECREASE, so the equal-count replacement form is not covered) | §2b: `test_registry_source_row_guard_refuses_marker_line_loss` (version guard blind; source-row-count guard refuses the count-drop fixture) |
| **B2** R4 is doctrine, not a catching rail | P1 | **RESIDUAL (policy)** — R4 removed from the catching-rail PASS and retained as an explicit policy residual | §4 (transcript replay only; no gate) |
| **B3** F-06 re-track asserted retired | P1 | **RESIDUAL** — overstatement retracted; a force-stage/ordering error can still re-track; no index/commit gate added | §2 (scope/residual) |
| **B4** C2 two-item claim is a row count | P1 | **CORRECTED** — C2's two rows are one connected improvisation chain; the basis is stated as for C6 | §6b; taxonomy §2/§4 |

**Overall release verdict after this convergence pass:** **PASS for the scoped remediation
set, at individual-signature scope.** The original blanket FAIL is discharged only for the
signatures each rail demonstrably refuses: R1 flags the **F-09** same-day-recording signature;
R2 refuses the **F-03** version-drain signature and the **F-04 count-decrease** form; R3 fails
on the **F-19** README/index drift signature; R5 names the **F-05** unresolvable-row fixture
signature. It is **not** a class-level PASS: F-01 remains a policy/detection residual (no
catching rail), F-04's equal-count replacement form is not caught by the count guard, and
F-08/F-11/F-12 (C4) and F-15/F-16 (C3) and F-17/F-18 (C5) are named as uncovered or
doctrine-only in §1b/§3/§5/§9. **R4 (C2)** and **F-06** are explicitly-retained residuals, not
counted. Every shipped assertion is bounded to the signature its rail demonstrably refuses.

---

## 1. R1 — "Recording is part of the act" — scope REDUCED to F-09 / F-01 (A1, A2)

**Doctrine** (rendered `AGENTS.md`; source `agent_config/rules.md`):

> "**Recording is part of the act.** A consequential act is not finished until it is recorded.
> Write the decision at the moment of the decision (`agentic-dynamics decision record`) and
> **close or explicitly park the session** (`agentic-dynamics session close`) — a record written
> in the retrospective is a reconstruction, not a record, and a session that does not write its
> close record has not closed. Cite a decision record only after its artifact exists. …"

### 1a. A1 — the coverage invariant is re-designed so a close cannot cover its own audit

**The old invariant.** `recording_sweep.scan()` covered a commit-day when it had a decision
**or any close** on that day. `scripts/session_close.py` ran the probe *after* writing the
close, so the close being checked became the evidence that covered the day it was auditing —
a self-mask. The p5 replay only exercised an uncovered day with **no** same-day close, and the
close-probe unit tests mocked `scan()`.

**The new invariant** (`scripts/recording_sweep.py`):

> A commit-day is covered by a decision record dated that day, or by a session close dated
> **strictly later** than the day. A close is a retrospective attestation of the days it
> follows; it never covers its own day.

**The rail flags the signature (run).** End-to-end through the REAL `session close` command
(no mocked `scan`), in a hermetic git repo + KB dir with a commit but no decision record:

```
$ python3 -m pytest tests/test_session_spine.py::TestRecordingProbe -q -p no:cacheprovider
6 passed
# test_same_day_close_cannot_cover_its_own_audit:
#   session close --session-date 2026-09-09 (real command, real scan)
#   -> recording.session_day_is_gap == True ; "2026-09-09" in gap_days   (the close did NOT cover it)
#   after materializing the day's decision record (the F-09 backfill)
#   -> recording.session_day_is_gap == False
$ python3 -m pytest tests/test_recording_sweep.py -q -p no:cacheprovider
7 passed
#   test_same_day_close_does_not_cover_its_own_day        -> 09-04 in gap_days
#   test_later_close_covers_earlier_days_and_decision...  -> later close covers 09-04; decision covers 09-09
```

**The historical moment it governs.** The close `session:2026-09-04-kb-facts-and-graph-repair`
cites `decision record 80f02d3ce5`, which did not exist until the 09-04 backfill
(`80f02d3ce520aa`); the unrecorded acts are the 09-09 audit
(`part@2026-09-10 01:00:39` "NOT recorded (no decision records): corpus migration, 402-row
tombstone disposition, CI fixture strategy…"; backfill `01:01:25`/`01:01:35`; close
`01:01:45`). Under the old invariant the 09-10 close covered the day it audited; under the new
invariant the same-day close is silent and the missing decision is the gap. — F-09.

**Verdict: PASS (re-designed; replayed same-day).**

### 1b. A2 — R1's claim is split by signature; the uncovered C4 signatures are named

R1's code (`recording_sweep` gap + phantom detector, plus the "close or explicitly park"
doctrine) covers **F-09** (recording-discipline gap / phantom claim) and **F-01** (session
never closed — the close/park clause). It does **not** add rails for the other C4 signatures;
the original p3 "C4 (F-08…F-12)" label was over-broad. Corrected attribution:

| C4 item | Signature | Covered by | Status |
|---|---|---|---|
| **F-09** | acts unrecorded until backfilled; close-record phantom | R1 (this branch) | **covered** (replayed §1a) |
| **F-01** | session abandoned, never closed | R1's "close or explicitly park" clause | **covered by doctrine** (no catching rail; the e2e probe now flags an unrecorded day) |
| **F-08** | unattributable double-registered finding rows (no producer path) | — | **UNCOVERED** — no producer-attribution check was added |
| **F-11** | stale `promotable` rows; promote did not close its own row | pre-existing in-window fix in `promote.py` (close-row-on-success + stale-tree refusal) | **not R1**; cite the in-window fix, do not claim R1 |
| **F-12** | `running` zombie rows; runner mints the row before validating the workdir | detection/reconciliation only (`control_sweep_zombies.py` sweeps heartbeat-expired `running` rows to `CANCELLED`) | **PARTIAL** — prevention not added |

The F-12 mechanism is still present at HEAD: the runner opens its control row before the engine
starts and before the clone/executors are built (`scripts/run_workflow.py:641-655`), so an
exception in that interval can still leave the historical no-heartbeat shape. No R1 claim
covers it.

**Verdict: PASS (claim reduced and re-scoped; F-08/F-11/F-12 explicitly not claimed).**

---

## 2. R2 — "Bulk mutation needs the store's convention" (C1) — now two bounded catching rails (A4 + B1)

**The p5 gap.** R2 shipped rule text only, and the original replay correctly recorded "none
(rule-only)". The adversarial held that a severity-5 class with **no** catching rail cannot
support a "top classes have catching rails" claim.

**The bounded catching rail (A4).** `scripts/generate_manifest.py` is the active path that
consumes the append-only `experiments/results/registry_index.jsonl`. That store only grows —
every supersede/tombstone APPENDS a line — so the number of distinct `knowledge_id` versions
is monotonic. The script now compares its compacted version count against the manifest already
on disk and **refuses to overwrite it with a smaller one** (exit 2), unless the operator passes
`--allow-shrink`:

```
$ python3 -m pytest tests/test_generate_manifest.py -q -p no:cacheprovider
20 passed
# test_detect_registry_drain_reports_the_direction: detect_registry_drain(new=2, prev=3) == (2,3)
# test_registry_drain_guard_refuses_a_smaller_compaction:
#   previous manifest = 5 versions; drained index compacts to 2 -> exit 2, manifest untouched
#   --allow-shrink -> exit 0 (the explicit, understood repair)
```

**The historical numeric proof.** The clause names exactly the F-03 operation — an append-only
store shrunk in a merge:

```
$ git diff --numstat 9bdb74059 9e4773fb1 -- experiments/results/registry_index.jsonl
1       43311   experiments/results/registry_index.jsonl
$ git show 9bdb74059:.../registry_index.jsonl | wc -l   # 48321
$ git show 9e4773fb1:.../registry_index.jsonl | wc -l   # 5011
```

Under the guard, the post-drain compaction (5,011 rows) can no longer replace the
pre-drain manifest (48,321 rows) without `--allow-shrink`. **This version-count guard alone
does not catch F-04** — the second adversarial review's B1. F-04's dedup deleted
tombstone/supersede **marker lines that deliberately share their target's `knowledge_id`**
(`corpus.md:161-188`), so the number of distinct `knowledge_id` versions can be unchanged while
real lifecycle evidence is lost. B1 is resolved by adding a second, strictly more sensitive
**raw-source-row-count drain guard** at the same mutation seam (§2b); the false claim that the
version guard catches F-04 is removed.

### 2b. B1 — the raw-source-row-count drain guard (replaces the F-04 over-claim)

`generate_manifest.py` now also records the count of structurally valid rows in the append-only
source (`registry_source_rows`) and refuses a compaction whose raw source-row count fell below
the previous manifest's (`detect_registry_source_drain`), at the same seam as the version guard.
Raw rows are monotonic for the same reason distinct versions are; counting them makes the F-04
**count decrease** visible even though the version count collapses the marker into its target's
slot. It is a raw-**count** guard, not identity/content conservation:

```
$ python3 -m pytest tests/test_generate_manifest.py -q -p no:cacheprovider
23 passed
# test_count_registry_source_rows_counts_marker_lines_sharing_a_knowledge_id:
#   3 raw rows, 2 distinct knowledge_id versions — the shared-id marker is COUNTED
# test_detect_registry_source_drain_reports_the_direction: (1,2) / None / None
# test_registry_source_row_guard_refuses_marker_line_loss (the F-04 count-decrease replay):
#   previous manifest: 1 version, registry_source_rows=2
#     (a full registration line + a supersede marker sharing kid_v1)
#   deduped index: 1 raw row (the marker deleted)
#   detect_registry_drain(compacted, 1) is None     <- the A4 version guard is BLIND to F-04
#   detect_registry_source_drain(1, 2) == (1, 2)    <- the B1 count guard SEES the drop
#   gm.main([]) == 2 ; stderr names F-04 ; the previous manifest is untouched
#   --allow-shrink -> exit 0 (the explicit, understood repair)
```

The guard is conservative in the same way as A4: an absent/corrupt previous manifest records no
source-row baseline, so the guard fails closed only on evidence (the first post-upgrade run
records the baseline rather than fabricating a claim).

**The bound (F1 of the third review).** This guard compares integer counts, nothing else. It
refuses a **count decrease** only; it cannot tell a lost tombstone/supersede marker from a
lost ordinary row, and it cannot see an **equal-count replacement** — a marker line deleted
and an unrelated valid row added in the same compaction leaves the raw count unchanged and is
**not** refused. Full row-identity/content conservation (hashing or set-comparing the source
rows across the previous and new compaction) would close that gap, but it was **not**
implemented: F1's first-stated correction — "rename and bound the rail" — is the change this
pass ships, and this paragraph is that bound.

**Scope / residual (stated honestly).** Both guards fire at the compaction seam — the active
path now that the index is untracked. They do not block a raw file edit that is never followed
by `manifest` regeneration, and `--allow-shrink` is a deliberate operator override. **F-06's
`git add -A` re-track vector is a retained residual, not retired (B3):** the corpus migration
makes an ordinary re-add unlikely (`experiments/results/` is untracked,
`git ls-files experiments/results | wc -l` = 0) and `test_publication_singular_door` guards the
producers, but neither prevents a force-stage (`git add -Af`) nor an ordering error that lands
the `add` before the ignore state — the repository's own `test_relabel_tree_gate.py` uses
`git add -Af`, demonstrating the index can still be forced. No index/commit gate was added. The
severity-5 drain path now has catching rails at the only place the store is consumed; they are
bounded, not universal, and F-06 is disclosed as residual rather than claimed caught.

**Verdict: PASS at signature scope (two bounded catching rails added and replayed — the
version-drain guard for F-03 and the raw-source-row-count drain guard for the F-04
count-decrease form; F-04's equal-count replacement form is NOT caught; F-06 disclosed
residual).**

---

## 3. R3 — "New work rides a worktree; regenerate the dependents" (C3) — PASS (unchanged)

**Doctrine** (rendered `AGENTS.md`; source `agent_config/rules.md`):

> "**New work rides a worktree; `main` gets only small derived-surface sweeps.** … when a
> generated surface changes, regenerate its dependents in the same wave (`python3
> scripts/_gen_instructions.py`, `python scripts/spec_status.py`, then the README count) — a
> derived surface and its source never drift on purpose."

**The wired rail flags the historical signature.** Running the CI gate in a detached worktree
at the pre-fix commit `24837b7d0` and at this branch's HEAD:

```
$ (cd <worktree 24837b7d0> && python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift)
exit=1
  DRIFT SCORE: 1
    [spec_lifecycle] STALE README.md:96
      claim: README.md:96 claims 191 specs (11 experiments + 180 workflows)
      code:  index.json holds 192 (11 experiments + 181 workflows)
$ (cd <branch HEAD> && python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift)
exit=0   (drift score 0)
```

**Historical moment.** The recording-rail chain (`f7d9ebe42` + `24837b7d0`) regenerated
`experiments/specs/index.json` but left `README.md:96` at 191 — F-19. The direct-`main`
commits the worktree clause addresses: `bb47441bc`, `292c47bad`, `ab887b5c8`, `77eb6c0b3`,
`9e4773fb1` — F-16.

**Verdict: PASS at signature scope — the gate fails on the exact historical commit (`F-19`,
the README/index drift) and is clean at HEAD.** The clause is *not* a catch for the other C3
rows: it does not detect F-15 wrong-command selection or F-16 direct-`main` work (those commit
shapes are cited only as context, not claimed covered).

---

## 4. R4 — "When the documented path fails, stop and record the gap" (C2) — POLICY RESIDUAL

**Doctrine** (rendered `AGENTS.md`; source `agent_config/rules.md`):

> "**When the documented path fails, stop and record the gap — do not build around it.** A
> failing rail is repaired, never replaced by a parallel mechanism. A net-new top-level
> mechanism — a new `scripts/*` entry point or an agent-spec wrapper — requires a one-line
> justification naming the gap it closes, and is reviewed like any other proposal. If a
> mechanism must be invented to finish a task, say so and stop; do not wrap the mistake."

**Rail:** none selected (rule-only) — a generic wrapper-necessity heuristic would be new,
low-precision machinery; `tests/test_script_classification.py` already fails a new
unclassified `scripts/*.py`. Replay is doctrine + transcript:

- F-13: `ses_f95ece514ffe… part@2026-09-10 02:10:50` (writes `scripts/launch_workflow.py`);
  controller alarm `02:11:34`; delete + admission `02:11:46` ("I was inventing a third
  launcher when the machinery already owns this").
- F-14: `part@2026-09-10 01:23:20` (agent-spec wrapper around the zero-model engine);
  admission `02:13:57` ("when the ask was ambiguous on shape, I built the bigger thing
  instead of asking").

**Verdict: POLICY RESIDUAL — not a catching-rail PASS.** R4 is directive and valuable, and
it is replayed against the transcript, but it does **not** catch the F-13/F-14 signatures: it
would not have stopped F-13 (the launcher was written and deleted after the controller
objected, before CI saw it) or F-14 (the wrapper landed as `f7d9ebe42`). It is therefore **not
counted** toward any "top classes have catching rails" condition (B2), and C2 carries no
automated new-mechanism gate — only `test_script_classification.py`'s existing (partial)
coverage and the directive text.

---

## 5. R5 — Publication-resolution guard (C5) — REDESIGNED as a fixture-tier resolver replay (A3)

**The p5 gap (A3).** The first R5 parsed only the committed `apps/website/data.js` and asserted
its `resolution_report` counters were zero; its "negative" replay mutated the report counter
itself. It loaded no registry, payload, waiver, or corpus root — a stale or falsified all-zero
report would pass. That is an artifact attestation, not the resolver replay p3 specified.

**The real rail (added).** `tests/test_build_data.py::test_fixture_tier_resolver_resolves_every_current_row_and_fails_on_one_unresolvable`
drives the REAL resolver (`canonical_corpus.load_canonical_tables`) over a hermetic fixture
manifest + payloads:

```
$ python3 -m pytest tests/test_build_data.py -k fixture_tier_resolver -q -p no:cacheprovider
1 passed
# positive: 3 current rows (story/review/finding) + 1 tombstoned
#   resolution.expected_current == 3 ; resolved == 3 ; unresolved == 0 ; complete is True
# negative: delete ONE payload -> missing == 1 ; the resolver NAMES the row
#   [("story", "s1")]  (the F-05 signature at fixture scale)
```

The pre-existing `data.js` attestation guard
(`test_data_js_resolution_report_is_complete_without_a_data_root`) is retained as a
**complementary artifact check**, explicitly scoped as such: it closes the publication half
(a broken corpus cannot ship as a clean-looking `data.js`), while the new test closes the
resolution half. The full-corpus re-resolution over the real 1.6 GB payload tree remains
`@requires_full_corpus` (local-only, documented migration tradeoff).

**Historical moment.** `build_data.py` hard-aborted on the unresolvable rows —
`ses_f92f8804affe… part@2026-09-05 17:55:14`/`17:55:20` ("publication aborted: current
registry rows could not be resolved…"); the 402 mis-registered rows were tombstoned at
`ddbca7545`; the prior CI contract test checked only `data.js`↔manifest identity and was
`@requires_full_corpus` (skipped in CI) — F-05.

**Verdict: PASS at signature scope — the fixture-tier resolver replay refuses the `F-05`
unresolvable-row signature (one payload removed → the row is named).** It is *not* a catch for
the other C5 rows: F-17's mount-provenance signature has no R5 rail, and F-18's heartbeat-TTL
assertion is the already-landed pre-existing half (`tests/test_fleet_guards.py`), not this
fixture resolution test. The full-registry re-resolution remains `@requires_full_corpus`.

---

## 6. Corpus and taxonomy corrections (A5, A6)

### 6a. A5 — the dirty-file count now cites its primary `git status` transcript part

A5's remaining requirement was not the number (already corrected to ~237) but the **primary
pointer that establishes it**. F-01's evidence list now cites the retained opening part
exactly, and the count is reproducible from it:

```
$ python3 -c "import sqlite3,json; ..."   # read-only query over the host transcript store
# part prt_06d0793c6001c5VS663QZ6oYh4, ses_f92f8804affe6ZZ0lH27Benpvc,
#   part@2026-09-04 17:26:48 (local; 15:26:48Z), command:
#   git status && git worktree list && git log --oneline -5
# -> modified: 1 ; untracked: 236 ; total (tab-prefixed status rows): 237
```

`docs/reviews/aio_controller_postmortem_corpus.md` (F-01) states **~237 files dirty at that
opening snapshot** citing that part (1 modified + 236 untracked), replacing the unsupported
"~292". The same correction is applied to the taxonomy's C6 narrative and the workflow spec's
`question`/g9 prompt. The corpus completeness claim is unchanged: every item still carries a
first-hand pointer.

**F4 bound (third review).** The 237 is an **opening-snapshot** count at 2026-09-04 17:26:48,
measured once. The corpus separately proves the interval 09-04 17:07 → 09-08 17:03 had **zero
git activity on any ref or stash**, but that is a statement about *commits*, not about which
paths stayed dirty: the retained `git status` does **not** show that the same 237 entries were
still present on 09-08. This pass removes the "dirty **for 4 days**" wording and asserts only
(a) the opening snapshot, and (b) the independently proven no-git-activity interval.

### 6b. A6 + B4 — the counting basis is stated, for C6 AND C2

The taxonomy's ≥2 threshold counts corpus **rows**, not independent incidents. §2 now states
this and records that **C6's two rows (F-01, F-02) are two symptoms of one incident chain**
(the same hammer session and the same 19-hour abandonment arc), and — per B4 — that **C2's two
rows (F-13, F-14) are two real acts in one connected improvisation chain** (F-14's wrapper
produced the F-12 failed launches, and F-12 triggered F-13's launcher draft). As independent
incidents **C2 and C6 are each a singleton**, so the "≥5 classes with ≥2 items" gate holds only
at the **row-count** grain (C1–C6 = 6 classes); by independent-incident count it is met by
**C1, C3, C4, C5 alone (4 classes)**. The taxonomy's §2 counting basis, the C2 and C6 class
details, and the completion log all carry the corrected statement; C2's row-count
classification is preserved.

**Verdict: PASS (both corrected in place; C2 and C6 each carry an explicit incident-chain
caveat rather than implying independence from a row count).**

---

## 7. A7 — the recording rail returns unmeasured and refuses mutation

**The p5 gap.** `python3 -B scripts/recording_sweep.py --scan` reported `GAPS: 12 uncovered
day(s)` and exit 1 in a source checkout with no runtime KB data: the sweep treated the absent
`experiments/results/kb` as zero decision/close coverage. A nightly run from a source checkout
could therefore produce false gaps and backfill reconstructions without evidence.

**The fix.** `scan()` now returns `{"status": "unmeasured", "reason": …}` when the runtime data
root is absent (or git is unavailable). `main` refuses every mode while unmeasured — `--scan`
and the default exit 2 with the reason; `--report` writes no audit; `--backfill` refuses to
mint a reconstruction. `session_close._recording_check` propagates the sweep's `unmeasured`
state rather than reading gaps out of a report the sweep declined to measure.

**The source-checkout replay (run, no runtime data root):**

```
$ python3 -B scripts/recording_sweep.py --scan
recording_sweep: UNMEASURED — no KB artifact dir on disk; refused to report or backfill
exit=2
$ python3 -B scripts/recording_sweep.py --backfill
recording_sweep: UNMEASURED — no KB artifact dir on disk; refused to report or backfill
exit=2
$ python3 -B scripts/recording_sweep.py --report    # exit 2; no audit.json written
exit=2
$ ls experiments/results/recording/audit.json       # No such file
```

Guard tests: `tests/test_recording_sweep.py::test_scan_is_unmeasured_when_the_runtime_data_root_is_absent`,
`::test_backfill_refuses_an_unmeasured_report`; the close-probe path in
`tests/test_session_spine.py::TestRecordingProbe` (6 passed).

**Verdict: PASS (unmeasured is first-class; report/backfill refuse).**

---

## 8. g10 — the fast path (REPAIRED)

**The reproduced failure.** The fast path (`pytest tests/ -m fast`) is the dependency-free
smoke the guards and g10 run. Three corpus-dependent modules were `fast`-marked in error
(`tests/test_lab_outputs_canonical.py`, `test_contribution_report.py`,
`test_publication_singular_door.py`):

- in a corpus-less checkout (exactly CI's fast-path step, which runs **before** the fixture
  restore) the unguarded `test_no_live_lab_output_carries_retired_summary_lineage` fails the
  smoke outright;
- on a host carrying the full runtime corpus, the `@requires_full_corpus` cases recompute over
  every payload, which is unbounded against the 180 s gate.

**The fix.** The three corpus-contract modules are no longer `fast`-marked (they run in the
full suite, where corpus work belongs), and the parallel-safety audit now forbids a
runtime-corpus dependency (`requires_(full_)?corpus`) in any `fast`-marked module, so the
dependency-free contract cannot silently regress.

**Replay (no runtime data root, the source-checkout condition):**

```
$ python3 -m pytest tests/ -m fast -q -p no:cacheprovider
533 passed, 2 skipped, 3430 deselected in 27.62s          # budget 180s
$ python3 -m pytest tests/test_fast_path_gate.py -q -p no:cacheprovider
3 passed in 33.66s                                          # includes the nested fast-path gate
$ python3 scripts/scan_docs_drift.py --check fast_path
DRIFT SCORE: 0  (fast_path 3/3 current)
```

The g10 gate itself (its fixed test list) is green:

```
$ python3 -m pytest tests/test_agent_config_render.py tests/test_doc_lifecycle.py \
    tests/test_script_classification.py tests/test_fast_path_gate.py \
    tests/test_dependency_direction.py tests/test_control_room_paths.py -q -p no:cacheprovider
54 passed in 34.31s
```

**Verdict: PASS (fast path green at ~27 s, well under the 180 s budget; audit hardened).**

---

## 9. Residuals (named, not claimed)

- **F-01 (C6/C4, session abandoned, never closed):** **policy/detection residual** — R1's
  "close or explicitly park" clause governs it and the recording probe flags an unrecorded day,
  but no rail intercepts a no-close abandonment; F-01 is **not** an R1 catch (F2). The corpus
  duration claim is also bounded to the opening snapshot + the no-git-activity interval (§6a).
- **F-08 (C4, unattributable emitter):** uncovered — no producer-attribution rail added.
- **F-11 (C4, stale promote rows):** not R1; covered by the in-window `promote.py`
  row-close fix (pre-existing, outside this remediation set).
- **F-12 (C4, row-before-workdir):** prevention not added; detection/reconciliation only via
  `control_sweep_zombies.py`; the runner still mints the row before validating the workdir
  (`scripts/run_workflow.py:641-655`).
- **F-15 / F-16 (C3, wrong-command selection / direct-`main` work):** **not caught by R3** —
  the docs-drift gate reproduces F-19 only; F-15/F-16 are named as context, not covered.
- **F-17 / F-18 (C5, mount provenance / heartbeat TTL):** **not caught by R5** — R5's
  fixture resolver reproduces F-05 only; F-18's TTL assertion is the pre-existing half, F-17
  has no rail in this set.
- **C1 version-drain guard (F-03):** bounded to the `generate_manifest.py` compaction seam; a
  raw edit never followed by `manifest` is not blocked; `--allow-shrink` is the operator
  override.
- **C1 raw-source-row-count drain guard (F-04):** the same seam, refusing a raw source-row
  **count decrease** so a lost tombstone/supersede marker (shared `knowledge_id`) is caught;
  same bounds. **The equal-count replacement form is not caught** — it is a count guard, not
  row-identity/content conservation (§2b).
- **C1 re-track vector (F-06):** **retained residual** — the corpus migration + `.gitignore`
  convention remove the ordinary path but a force-stage or an add-before-ignore ordering error
  can still re-track; no index/commit gate was added (B3).
- **R4 (C2):** **explicit policy residual** — no automated wrapper/new-mechanism gate; R4 is
  replayed against the F-13/F-14 transcript but is **not** a catching-rail PASS (B2).
- **R5 full registry re-resolution:** remains `@requires_full_corpus` (local-only); the
  fixture-tier replay and the artifact attestation cover the CI-runnable half.
- **P1/P3 parked** as in p3 §5 (C6 watchdog, C2 wrapper test) — unchanged. **P2 (C1
  volume/ordering assertion) is partly discharged** by §2b's manifest-seam count guard; only
  a pre-commit/CI staged-tree form remains parked, since the tracked-store vector F-06 names is
  itself a disclosed residual with no index/commit gate (B3).
- **A4/B1 verdict note:** the top severity-5 class's **registry path** now carries **two
  bounded, signature-scoped rails** (the F-03 version drain guard and the F-04 raw-source-row
  **count-decrease** guard) rather than none; the durability of both guards is bounded as stated
  above, F-04's equal-count replacement form is disclosed uncovered, and F-06 remains a
  disclosed residual. This is a signature-scope discharge, not a class-level one.

---

## 10. Verification completion log

- **DONE_WHEN — every selected remediation shows replay evidence:** PASS (R1 e2e same-day; R2
  version drain guard + B1 raw-source-row-count drain guard; R3 historical commit gate; R5
  fixture-tier resolver; R4 transcript only). A1–A7 each carry a replay in §0/§1–§7; the second
  adversarial review's B1–B4 each carry a disposition in §0b, with B1 replayed in §2b.
- **DONE_WHEN — the verify doc records pass/revert per item:** PASS (R1 PASS re-designed;
  R2 PASS + two bounded rails, both at signature scope; R3 PASS at signature scope; **R4 policy
  residual — not a PASS**; R5 PASS at signature scope; A5/A6/A7/g10 PASS; B4 corrected; F1–F4
  narrowed; no reverts).
- **DONE_WHEN — no remediation shipped unverified:** PASS — every claim above is a command
  that was run on this branch; the original p5 headline is retracted where it overclaimed; R4,
  F-01 and F-06 are disclosed residuals, not claims.
- **Release predicate (signature-level — exactly true):** PASS — the following, and only the
  following, signatures are demonstrably refused by their rails:
  - **R1 → F-09** (same-day recording gap; §1a). F-01 is a policy/detection residual, not a
    catch.
  - **R2 → F-03** (append-only version drain) and the **F-04 count-decrease** form (§2/§2b).
    F-04's **equal-count replacement** form is *not* caught; F-06 is a disclosed residual.
  - **R3 → F-19** (README/index drift; §3). F-15/F-16 are *not* caught.
  - **R5 → F-05** (fixture-tier unresolvable row; §5). F-17/F-18 are *not* caught.
  Class-level coverage is expressly **not** claimed for C1–C6.
- **Gates (re-run in this claim-narrowing pass):** `python3 scripts/_gen_instructions.py
  --check` → surfaces OK (38 files); `python3 -m pytest tests/test_generate_manifest.py
  tests/test_build_data.py tests/test_recording_sweep.py tests/test_session_spine.py
  tests/test_doc_lifecycle.py tests/test_agent_config_render.py -q` → **143 passed, 3 skipped**;
  fast path **533 passed, 2 skipped / 27.56s** (budget 180s); g10 list **54 passed / 33.44s**;
  `python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift` → drift score 0
  (exit 0); `ruff` on `scripts/generate_manifest.py` + `tests/test_generate_manifest.py` clean.
- **LOG:** PASS.
