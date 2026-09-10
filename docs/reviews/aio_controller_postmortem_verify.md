---
status: accepted
---

# AIO controller postmortem — replay verification (p5)

**Inputs:** the p4 branch (`61c4c97fe`) + the p0 corpus (`d19ef95a9`) and p3 design
(`f03a8d1fe`).
**Role:** replay each selected remediation (R1–R5) against its historical class and record the
outcome. A remediation that does not demonstrably catch its class is reverted or re-designed
here — never shipped unverified.

**Headline result:** **4 of 5 pass as applied; R1 was re-designed in this phase** (the
verification falsified the original detector — see §3). All five are committed verified.

**Environment note.** `experiments/results/**` is untracked runtime data and is absent from
this worktree, so replays use hermetic copies / detached worktrees of historical commits where
a data root would otherwise be required. Every command below was run on this branch.

---

## 1. Summary

| ID | Class (items) | Doctrine clause | Rail replay | Verdict |
|---|---|---|---|---|
| R1 | C4 (F-08…F-12) + C6 clause | "Recording is part of the act" | `recording_sweep.scan()` on a hermetic historical KB → flags the gap day + the short-prefix phantom | **PASS (re-designed)** |
| R2 | C1 (F-03, F-04, F-06) | "Bulk mutation needs the store's convention" | none (rule-only, vector retired) — historical numeric proof + transcript | **PASS** |
| R3 | C3 (F-15, F-16, F-19) | "New work rides a worktree; … regenerate the dependents" | wired CI gate run in a detached worktree at the pre-fix commit → **exit 1**, names README:96 | **PASS** |
| R4 | C2 (F-13, F-14) | "When the documented path fails, stop and record the gap" | none (rule-only) — historical transcript | **PASS** |
| R5 | C5 (F-05; F-17/F-18 context) | n/a (rail-only) | test on the committed data.js → pass; mutated `missing: 402` → **fail** | **PASS (scoped)** |

---

## 2. Per-remediation replay

### R1 — "Recording is part of the act" (C4; carries the C6 clause) — PASS (re-designed)

**Doctrine now says what the class violated** (rendered `AGENTS.md:61`, source
`agent_config/rules.md`):

> "**Recording is part of the act.** A consequential act is not finished until it is recorded.
> Write the decision at the moment of the decision (`agentic-dynamics decision record`) and
> **close or explicitly park the session** (`agentic-dynamics session close`) — a record written
> in the retrospective is a reconstruction, not a record, and a session that does not write its
> close record has not closed. Cite a decision record only after its artifact exists. …"

**The extended rail flags the signature.** The close-time probe calls the existing
`recording_sweep.scan()`; the hermetic replay (`/tmp/r1_replay`, a temp git repo with a
2026-09-04 commit covered by a close and an unrecorded 2026-09-09 commit, plus a close artifact
citing `decision record 80f02d3ce5` with no artifact):

```
REPLAY A (decision artifact ABSENT) — the historical state:
  gap_days: ['2026-09-09']
  phantom_close_claims: ['aaaaaaaaaaaa: cites 80f02d3ce5... (no artifact)']
REPLAY B (decision artifact materialized) — after the backfill:
  phantom_close_claims: []
```

The close-time probe surfaces exactly this in `--json` (`recording.gap_days` /
`recording.phantom_close_claims`) and as a stderr warning; it is best-effort and
`unmeasured`-aware (a checkout without the data root reports `unmeasured`, never a fabricated
gap) — pinned by 5 tests in `tests/test_session_spine.py`.

**The historical moment it governs.**
- The phantom: close `session:2026-09-04-kb-facts-and-graph-repair` (kb artifact
  `0bd5105085aa7fd0`) cites `decision record 80f02d3ce5`, which did not exist until the 09-04
  backfill (`80f02d3ce520aa`, category `merge`). — F-09.
- The unrecorded acts: `opencode.db ses_f95ece514ffe… part@2026-09-10 01:00:39` ("NOT recorded
  (no decision records): corpus migration, 402-row tombstone disposition, CI fixture
  strategy…"); backfill at `part@2026-09-10 01:01:25` / `01:01:35`; close at `01:01:45`.
- The un-closed session: the hammer's last part `ses_f92f8804affe… part@2026-09-05 17:56:04`
  (no close record) — F-01 — is what the "close or explicitly park" clause governs.

**Verdict:** PASS after the §3 re-design.

### R2 — "Bulk mutation needs the store's convention" (C1) — PASS

**Doctrine** (rendered `AGENTS.md:68`):

> "**Bulk mutation needs the store's convention.** Before any bulk mutation of a durable store
> or of git's index/refs — a merge, a dedup, `git add -A`, `git rm --cached`, a history rewrite —
> apply the store's documented convention and prove the direction is safe. Append-only stores
> merge by **union**, never by taking a side; a dedup keeps only **full-row-equal** duplicates;
> the `.gitignore` lands before the `add`. An operation that shrinks an append-only store is a
> violation until proven otherwise."

**Rail:** none selected, by design — the tracked-store vector was retired by the corpus
migration (`ab887b5c8`), so an assertion would be new machinery for a gone vector (p3 §5 P2).
The replay is therefore doctrine + the historical numeric/transcript moment (the prompt's
"quote the clause + cite the transcript" path):

**Historical moment.**
- The Sep-4 drain — an append-only store shrunk in a merge:
  `git diff --numstat 9bdb74059 9e4773fb1 -- experiments/results/registry_index.jsonl` = `1  43311`
  (commit `9e4773fb1`). The clause names this exact operation a violation. — F-03.
- The dedup over-deletion: `ses_f95ece514ffe… part@2026-09-08 17:05:36` (`48324 -> 20132 rows`);
  self-caught at `part@2026-09-08 17:24:03` ("**my dedup was wrong**"). — F-04.
- `git add -A` before the ignore: `part@2026-09-08 23:23:36`. — F-06.

**Verdict:** PASS (doctrine + history). Residual: no automated volume/ordering rail
(parked P2); the rule is directive and names the exact convention violated.

### R3 — "New work rides a worktree; regenerate the dependents" (C3) — PASS

**Doctrine** (rendered `AGENTS.md:74`):

> "**New work rides a worktree; `main` gets only small derived-surface sweeps.** … when a
> generated surface changes, regenerate its dependents in the same wave (`python3
> scripts/_gen_instructions.py`, `python scripts/spec_status.py`, then the README count) — a
> derived surface and its source never drift on purpose."

**The wired rail flags the historical signature.** The CI `surfaces` job now runs
`python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift`. Run in a detached
worktree at the pre-fix commit `24837b7d0` (README 191, index 192):

```
$ git worktree add --detach /tmp/replay_f19 24837b7d0
$ (cd /tmp/replay_f19 && python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift)
exit=1
  spec_lifecycle              1        0       1        0       1
  DRIFT SCORE: 1
  findings:
    [spec_lifecycle]
      STALE    README.md:96
               claim: README.md:96 claims 191 specs (11 experiments + 180 workflows)
               code:  index.json holds 192 (11 experiments + 181 workflows)
```

At the branch HEAD the same gate exits `0` (drift score 0). The existing
`tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index` is the test-level twin.

**Historical moment.** The recording-rail chain (`f7d9ebe42` + `24837b7d0`, 09-10) regenerated
`experiments/specs/index.json` but did not resync the README — F-19. And the direct-`main`
commits the worktree clause addresses: `bb47441bc`, `292c47bad`, `ab887b5c8`, `77eb6c0b3`,
`9e4773fb1` (all on the `main` checkout) — F-16, which the 09-09 close names as the live
permanence gap.

**Verdict:** PASS — the gate fails on the exact historical commit and passes on the fixed one.

### R4 — "When the documented path fails, stop and record the gap" (C2) — PASS

**Doctrine** (rendered `AGENTS.md:81`):

> "**When the documented path fails, stop and record the gap — do not build around it.** A
> failing rail is repaired, never replaced by a parallel mechanism. A net-new top-level
> mechanism — a new `scripts/*` entry point or an agent-spec wrapper — requires a one-line
> justification naming the gap it closes, and is reviewed like any other proposal. If a
> mechanism must be invented to finish a task, say so and stop; do not wrap the mistake."

**Rail:** none selected (rule-only, p3 §5 P3) — a generic wrapper-necessity heuristic would be
new, low-precision machinery; the existing `tests/test_script_classification.py` already fails a
new unclassified `scripts/*.py`. Replay is doctrine + transcript:

**Historical moment.**
- F-13: `ses_f95ece514ffe… part@2026-09-10 02:10:50` (writes `scripts/launch_workflow.py`);
  controller alarm `part@2026-09-10 02:11:34`; delete + admission `part@2026-09-10 02:11:46`
  ("I was inventing a third launcher when the machinery already owns this").
- F-14: `part@2026-09-10 01:23:20` (agent-spec wrapper around the zero-model engine);
  admission `part@2026-09-10 02:13:57` ("when the ask was ambiguous on shape, I built the
  bigger thing instead of asking").

**Verdict:** PASS (doctrine + history). Residual: no automated wrapper gate (parked P3).

### R5 — Publication-resolution guard (C5) — PASS (scoped)

**Rail** (`tests/test_build_data.py::test_data_js_resolution_report_is_complete_without_a_data_root`),
runs in CI with no data root. Positive on the committed artifact; negative on the class
signature (a data.js carrying unresolved rows), replayed in a detached worktree at HEAD with
`resolution_report.missing` set to the historical 402:

```
$ python3 -m pytest tests/test_build_data.py -k resolution_report_is_complete   # committed
1 passed
$ (mutate /tmp/replay_r5/apps/website/data.js: "missing": 402)
$ python3 -m pytest tests/test_build_data.py -k resolution_report_is_complete   # mutated
E   assert 402 == 0
FAILED tests/test_build_data.py::test_data_js_resolution_report_is_complete_without_a_data_root
```

**Historical moment.** `build_data.py` hard-aborted on the unresolvable rows —
`ses_f92f8804affe… part@2026-09-05 17:55:14` / `17:55:20` ("publication aborted: current
registry rows could not be resolved…"); the 402 mis-registered rows were tombstoned at
`ddbca7545`; the prior CI contract test checked only `data.js`↔manifest identity and was
`@requires_full_corpus` (skipped in CI) — F-05.

**Scope (recorded honestly).** The guard asserts the **published artifact's** resolution
attestation is present and failure-free; it does not re-resolve the on-disk registry (the CI
fixture carries no payloads, so that assertion remains `@requires_full_corpus`, local-only —
the documented migration tradeoff). Its role is fail-closed prevention: an artifact regenerated
from a broken registry cannot ship as a clean-looking `data.js`. The C5 sibling signatures
F-17 (container provenance) and F-18 (heartbeat TTL) are context; the TTL assertion landed
in-window in `tests/test_fleet_guards.py`.

**Verdict:** PASS (published-signature replay); full registry re-resolution explicitly out of
scope.

---

## 3. Re-designed in this phase (R1)

The first R1 attempt **did not demonstrably catch F-09's phantom**, and verification caught it:

- The existing `recording_sweep._phantom_close_claims()` matched only a **64-hex** id
  (`r"decision record ([0-9a-f]{64})"`), but the corpus cites the **short human form** —
  `…, decision record 80f02d3ce5` (10 hex). Replay with the original regex: **no match, no
  phantom** (a missed catch).
- **Re-design applied:** the detector now matches a **prefix** (6–64 hex) and treats the
  citation as a phantom when no known artifact stem starts with it; documented in the function
  docstring. Replay after the fix flags the historical citation (§2-R1) and clears when the
  artifact exists.
- Guarded by the new `tests/test_recording_sweep.py` (4 tests: short-prefix phantom, clears on
  artifact, full-hex happy path, gap scan). `ruff` clean; suite green.

This is the phase's most important result: the postmortem's own instrument was itself
under-firing, and the replay found and fixed it.

---

## 4. Residuals (parked, unchanged from p3 §5)

- **P1 — C6 interactive-session / uncommitted-work watchdog:** parked; covered by R1's
  "close or explicitly park" clause.
- **P2 — C1 volume/ordering assertion:** parked; tracked-store vector retired by the
  migration.
- **P3 — C2 wrapper-necessity test:** parked; R4's justification clause is the cover.
- **P4 — R (environmental):** no action; fixed by the corpus migration + `snapshot:false`.
- **R5 full registry re-resolution:** remains `@requires_full_corpus`; documented.

---

## 5. Verification completion log

- **DONE_WHEN — every selected remediation shows replay evidence:** PASS (R1 hermetic rail run;
  R2 numeric + transcript; R3 wired CI gate on the historical commit; R4 transcript; R5
  positive/negative rail run).
- **DONE_WHEN — the verify doc records pass/revert per item:** PASS (5/5 PASS; R1 re-designed
  in-phase and re-verified; no reverts).
- **DONE_WHEN — no remediation shipped unverified:** PASS (R1 rebased on the falsification;
  R5's scope limitation stated explicitly).
- **Gates:** `python3 scripts/_gen_instructions.py --check` → surfaces OK; focused suite →
  `90 passed, 3 skipped` (recording-sweep/session-spine/build-data/doc-lifecycle); `ruff check`
  on touched files → clean.
- **LOG:** PASS.
