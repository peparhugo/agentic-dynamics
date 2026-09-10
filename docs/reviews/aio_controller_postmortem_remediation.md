---
status: accepted
---

# AIO controller postmortem — remediation design (p3)

**Inputs:** `docs/reviews/aio_controller_postmortem_defenses.md` (p2, commit `1e5b928f3`);
`docs/reviews/aio_controller_postmortem_taxonomy.md` (p1); `…corpus.md` (p0).
**Role:** design the **minimal change set** — one remediation per class with a gap, exact
proposed rule text, a replay test (executed in p5), and blast radius. Rank by cost/leverage,
cap at the **top 5**, park the rest.

**Design principles honored**
1. **Rule text first** (`agent_config/rules.md`), **existing rail second**, **new machinery
   only with justification** — and this design proposes **no new machinery**: every rail
   below is an existing script/test/CI job extended.
2. **One remediation per class.** R1 also carries the one clause that partially covers C6
   (close-or-park), so C6 needs no separate selected item.
3. Each change is verifiable by **replay of a historical artifact** in p5, not by assertion.

---

## 1. Selection (top 5 by cost/leverage)

| Rank | ID | Class (items) | Remediation | Kind | Replay target |
|---|---|---|---|---|---|
| 1 | **R1** | C4 (F-08…F-12) + C6 clause | "Recording is part of the act" + `session_close` runs the existing sweep | rule text + rail extension | F-09 phantom/backfill; F-01 no-close |
| 2 | **R2** | C1 (F-03, F-04, F-06) | "Bulk mutation needs the store's convention" | rule text only (vector retired) | F-03 drain diff; F-04 dedup; F-06 `add -A` |
| 3 | **R3** | C3 (F-15, F-16, F-19) | "Follow the documented shape; regenerate the dependents" + wire docs-drift into CI | rule text + rail extension | F-16 direct-main; F-19 README drift |
| 4 | **R4** | C2 (F-13, F-14) | "When the documented path fails, stop and record the gap" | rule text only | F-13 launcher; F-14 wrapper |
| 5 | **R5** | C5 (F-05, F-17, F-18) | Publication-**resolution** assertion in the CI fixture tier (+ TTL invariant, already present) | existing test extension | F-05 402 rows; F-18 heartbeat |
| — | parked | C6 rail, C1 rail, C2 wrapper test, R | see §5 | — | — |

**Why this order.** R1 targets the largest class (5 items) with a one-bullet rule + a call
into an already-written sweep. R2 targets the highest-severity item (F-03, sev 5) and costs
one bullet because the corpus migration has already retired the tracked-store vector. R3 is
half-closed already (the README assertion exists) and finishes with a one-line CI wiring.
R4 is a one-bullet clarification. R5 is a test-predicate strengthening (rails exist). R1's
rule text includes the "close or explicitly park the session" clause, which is the doctrine
C6/F-01 violated — so C6 is covered by a selected item and its independent rail is parked.

---

## 2. Selected remediations — exact text, rail, replay, blast radius

### R1 — "Recording is part of the act" (C4; carries one C6 clause)

**Exact proposed text — `agent_config/rules.md`, a new bullet appended to the AUTHORITY
list (after the "One writer per plane" bullet, currently line 55):**

> - **Recording is part of the act.** A consequential act is not finished until it is
>   recorded. Write the decision at the moment of the decision
>   (`agentic-dynamics decision record`) and **close or explicitly park the session**
>   (`agentic-dynamics session close`) — a record written in the retrospective is a
>   reconstruction, not a record, and a session that does not write its close record has not
>   closed. Cite a decision record only after its artifact exists. The AIO's own rule
>   (2026-09-09 discipline audit): every consequential act gets its decision record at the
>   moment of the act, not in the retrospective.

**Rail extension (existing rail).** In `scripts/session_close.py`, immediately after the
close + reflection append succeed, call the already-written `recording_sweep.scan()` and:
- include `"recording": {"gap_days": [...], "phantom_close_claims": [...]}` in the `--json`
  report, and
- print a one-line `WARNING` to stderr when the session's own `session_date` appears in
  `gap_days`, or when any `phantom_close_claims` exist.
It remains **best-effort**: a sweep failure is a warning, exit stays 0, the durable close
still lands (same contract as the reflection append). No new file, no new mechanism.

**DONE_WHEN (replay in p5).**
1. Quote the new bullet verbatim and cite the historical moment it governs:
   `opencode.db ses_f95ece514ffe… part@2026-09-10 01:00:39` ("NOT recorded (no decision
   records): corpus migration, 402-row tombstone disposition, …").
2. Run `recording_sweep.scan()` against a **hermetic copy** of the KB artifact dir with the
   backfilled decision `80f02d3ce5` removed — the historical F-09 state — and show
   `phantom_close_claims` naming the `kb-facts-and-graph-repair` close that cited it. (In the
   live dir the phantom is gone because it was backfilled; the hermetic replay is the proof.)
3. Cite F-01's terminal part (`ses_f92f8804affe… part@2026-09-05 17:56:04`) as the session the
   "close or explicitly park" clause governs.

**Blast radius.** `agent_config/rules.md` → regenerate with `python3
scripts/_gen_instructions.py`, which re-renders the root `AGENTS.md` + `CLAUDE.md` and the
`.opencode/` + `.claude/` surfaces (`_gen_instructions.py --check` names the exact stale
set). Code: `scripts/session_close.py` + a test in `tests/test_session_close.py` (or
`tests/test_recording_sweep.py`). No schema, no CLI, no new file.

---

### R2 — "Bulk mutation needs the store's convention" (C1)

**Exact proposed text — `agent_config/rules.md`, a new bullet in the AUTHORITY list (after
R1's bullet):**

> - **Bulk mutation needs the store's convention.** Before any bulk mutation of a durable
>   store or of git's index/refs — a merge, a dedup, `git add -A`, `git rm --cached`, a
>   history rewrite — apply the store's documented convention and prove the direction is
>   safe. Append-only stores merge by **union**, never by taking a side; a dedup keeps only
>   **full-row-equal** duplicates; the `.gitignore` lands before the `add`. An operation that
>   shrinks an append-only store is a violation until proven otherwise.

**Rail: none selected — justified.** The only tracked append-only store in the window
(`experiments/results/registry_index.jsonl`) was **untracked** by the corpus migration
(`ab887b5c8`), which retires the git-merge drain vector (F-03). A remaining assertion on an
untracked file (or a pre-commit hook on a path that no longer exists) would be **new
machinery for a vector that is already gone**. The rule text is the minimal remediation; a
volume/ordering assertion is parked (§5, P2) pending evidence the store is re-tracked.

**DONE_WHEN (replay in p5).**
1. Quote the bullet against F-03's numeric proof —
   `git diff --numstat 9bdb74059 9e4773fb1 -- experiments/results/registry_index.jsonl` =
   `1 43311` (an append-only store shrunk by 43,311 lines in one merge). The clause names
   exactly this as a violation.
2. Quote it against F-04 (`ses_f95ece514ffe… part@2026-09-08 17:05:36`, dedup
   `48324 -> 20132`) and F-06 (`part@2026-09-08 23:23:36`, `add -A` before the ignore).

**Blast radius.** `agent_config/rules.md` → the generated instruction surfaces only
(`AGENTS.md`, `CLAUDE.md`, `.opencode/`, `.claude/`) via `_gen_instructions.py`. No code.

---

### R3 — "Follow the documented shape; regenerate the dependents" (C3; one C6 clause)

**Exact proposed text — `agent_config/rules.md`, a new bullet in the AUTHORITY list (after
R2's bullet):**

> - **New work rides a worktree; `main` gets only small derived-surface sweeps.** Permanence
>   work — a feature, a migration, a data-plane change, a merge of an append-only log —
>   rides a `feature/*` branch through the permanence gate. Follow the documented
>   command/runner shape the skills and `scripts/CONTEXT.md` name; when a generated surface
>   changes, regenerate its dependents in the same wave (`python3
>   scripts/_gen_instructions.py`, `python scripts/spec_status.py`, then the README count) —
>   a derived surface and its source never drift on purpose.

**Rail extension (existing script + CI).** Add
`python3 scripts/scan_docs_drift.py --fail-on-drift` to the CI `test`/`surfaces` job in
`.github/workflows/pytest.yml`. The script already exists and re-derives seven axes
(`spec_lifecycle`, `manifest_counts`, `fast_path`, …); it currently only reports. This turns
generated-surface drift (the F-19 class) into a red build without a new mechanism.

**DONE_WHEN (replay in p5).**
1. Quote the worktree clause against F-16 (`bb47441bc`, `292c47bad`, `ab887b5c8`,
   `77eb6c0b3`, `9e4773fb1` all committed on the `main` checkout) and the 09-09 close's
   open-thread "branch protection bypassed via `enforce_admins:false`".
2. Run `python3 scripts/scan_docs_drift.py --fail-on-drift` at the current branch HEAD and
   show it exits **1** on the README/spec-index drift (F-19) — the wired rail catching the
   class. (The existing `tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index`
   demonstrates the same at test level.)

**Blast radius.** `agent_config/rules.md` → generated instruction surfaces;
`.github/workflows/pytest.yml`. No new code. (If the workflow-v1 linter/schema is used, its
renders are unaffected.)

---

### R4 — "When the documented path fails, stop and record the gap" (C2)

**Exact proposed text — `agent_config/rules.md`, a new bullet in the AUTHORITY list (after
R3's bullet):**

> - **When the documented path fails, stop and record the gap — do not build around it.** A
>   failing rail is repaired, never replaced by a parallel mechanism. A net-new top-level
>   mechanism — a new `scripts/*` entry point or an agent-spec wrapper — requires a one-line
>   justification naming the gap it closes, and is reviewed like any other proposal. If a
>   mechanism must be invented to finish a task, say so and stop; do not wrap the mistake.

**Rail: none selected — justified.** `tests/test_script_classification.py` already fails a
new unclassified `scripts/*.py`; the exposed gap is a **YAML agent-spec wrapper**, which
needs a bespoke "is this wrapper necessary" heuristic — not minimal, and would be new
machinery. Rule text is the minimal remediation; the wrapper test is parked (§5, P3).

**DONE_WHEN (replay in p5).**
1. Quote the bullet against F-13 (`ses_f95ece514ffe… part@2026-09-10 02:10:50` write of
   `scripts/launch_workflow.py`; `02:11:46` delete; "I was inventing a third launcher when
   the machinery already owns this").
2. Quote it against F-14 (`part@2026-09-10 01:23:20` wrapper write) and the AIO's own
   admission `part@2026-09-10 02:13:57` ("when the ask was ambiguous on shape, I built the
   bigger thing instead of asking").

**Blast radius.** `agent_config/rules.md` → generated instruction surfaces only. No code.

---

### R5 — Publication-resolution assertion in the CI fixture tier (C5)

**Rail extension (existing test).** Strengthen the publication-contract test so the CI
fixture tier asserts **resolution**, not identity: every current registry row in the
committed corpus fixture resolves to a measurement payload **or** carries a sanctioned
waiver/tombstone. Concretely, extend `tests/test_build_data.py` (and its
`requires_corpus`/fixture sibling) with a resolution assertion that runs against the 13 MB
CI fixture (`237bed6dd`), and keep the existing heartbeat-TTL assertion in
`tests/test_fleet_guards.py` (added in-window for F-18). No new test file, no new rail.

**DONE_WHEN (replay in p5).**
1. Run the resolution assertion against the clean committed fixture → **PASS**.
2. Inject one unresolvable row into a **copy** of the fixture (payload removed) → the
   assertion **FAILS** with the row named — the historical F-05 signature (`build_data.py`
   `_assert_resolution_complete`; the 402-row tombstone `ddbca7545`).
3. Cite F-17's provenance signature (a reader pointed at the wrong root) as the reason the
   assertion also pins the corpus root, and F-18's TTL assertion as the already-landed half.

**Blast radius.** `tests/test_build_data.py` (+ the corpus fixture if a row is added to
exercise the failure path — prefer a hermetic temp copy, no fixture change). No rule text,
no generated surface.

---

## 3. Proposed rules.md change (all rule text in one block)

For p4, the exact block to append to the **AUTHORITY** list in `agent_config/rules.md`
(after line 55, `"… each projector owns its own row."`):

```markdown
- **Recording is part of the act.** A consequential act is not finished until it is
  recorded. Write the decision at the moment of the decision
  (`agentic-dynamics decision record`) and **close or explicitly park the session**
  (`agentic-dynamics session close`) — a record written in the retrospective is a
  reconstruction, not a record, and a session that does not write its close record has not
  closed. Cite a decision record only after its artifact exists. The AIO's own rule
  (2026-09-09 discipline audit): every consequential act gets its decision record at the
  moment of the act, not in the retrospective.
- **Bulk mutation needs the store's convention.** Before any bulk mutation of a durable
  store or of git's index/refs — a merge, a dedup, `git add -A`, `git rm --cached`, a
  history rewrite — apply the store's documented convention and prove the direction is
  safe. Append-only stores merge by **union**, never by taking a side; a dedup keeps only
  **full-row-equal** duplicates; the `.gitignore` lands before the `add`. An operation that
  shrinks an append-only store is a violation until proven otherwise.
- **New work rides a worktree; `main` gets only small derived-surface sweeps.** Permanence
  work — a feature, a migration, a data-plane change, a merge of an append-only log —
  rides a `feature/*` branch through the permanence gate. Follow the documented
  command/runner shape the skills and `scripts/CONTEXT.md` name; when a generated surface
  changes, regenerate its dependents in the same wave (`python3
  scripts/_gen_instructions.py`, `python scripts/spec_status.py`, then the README count) —
  a derived surface and its source never drift on purpose.
- **When the documented path fails, stop and record the gap — do not build around it.** A
  failing rail is repaired, never replaced by a parallel mechanism. A net-new top-level
  mechanism — a new `scripts/*` entry point or an agent-spec wrapper — requires a one-line
  justification naming the gap it closes, and is reviewed like any other proposal. If a
  mechanism must be invented to finish a task, say so and stop; do not wrap the mistake.
```

**Reads as directive, not suggestion:** each bullet names a hard boundary ("is a violation",
"never", "do not") and a concrete command or artifact. R1/R3 additionally have a runnable
rail (session-close sweep call; CI docs-drift gate), which is the review's complaint
("prose that tells it to behave better without rails") addressed for the two classes where an
existing rail suffices.

---

## 4. Blast-radius summary (what regenerates)

| Remediation | Rule text? | Code/test touched | Generated surfaces to regenerate | CI |
|---|---|---|---|---|
| R1 | yes | `scripts/session_close.py` + test | `AGENTS.md`, `CLAUDE.md`, `.opencode/`, `.claude/` (`_gen_instructions.py`) | render check |
| R2 | yes | none | same renders | render check |
| R3 | yes | none | same renders + `.github/workflows/pytest.yml` | render check; docs-drift `--fail-on-drift` |
| R4 | yes | none | same renders | render check |
| R5 | no | `tests/test_build_data.py` (+ `test_fleet_guards.py` already) | none | test job |

`python3 scripts/_gen_instructions.py --check` is the gate for every rule-text item (R1–R4);
R5 is code-only. Because R1–R4 all edit the single neutral source `agent_config/rules.md`,
p4 applies **one** edit + **one** regeneration for all four bullets.

---

## 5. Parked (not selected; with reasons)

- **P1 — C6 interactive-session / uncommitted-work supervisor flag (flag-only).**
  Parked: R1's "close or explicitly park the session" clause is the selected doctrine for
  this class; the rail is a new flag-only watchdog (non-trivial) and the in-run
  `checkpoint: true` gate + phase watchdog already cover workflow phases.
- **P2 — C1 append-only volume/ordering assertion.** Parked: the tracked-store vector is
  retired by the corpus migration; an assertion on an untracked file is new machinery for a
  gone vector. Revisit if a durable store is re-tracked.
- **P3 — C2 wrapper-necessity test.** Parked: a generic "is this YAML wrapper necessary"
  heuristic is new machinery and low-precision; R4's justification bullet is the minimal
  cover. Revisit if a wrapper lands again.
- **P4 — R (environmental).** No action: fixed by the corpus migration (`ab887b5c8`) +
  `snapshot:false`. A snapshot-cost metric is not justified.

---

## 6. Remediation-design completion log

- **DONE_WHEN — each selected remediation has exact text + a replay test:** PASS (R1–R5;
  §2 and §3).
- **DONE_WHEN — nothing creates new machinery where an existing rail suffices:** PASS (R1
  calls the existing `recording_sweep`; R3 wires the existing `scan_docs_drift`; R5 extends
  an existing test; R2/R4 are rule-only with the missing rail explicitly justified as
  new-machinery-for-a-retired-vector).
- **DONE_WHEN — capped at 5, rest parked:** PASS (§1, §5).
- **DONE_WHEN — one remediation per class with a gap:** PASS (C1→R2, C2→R4, C3→R3, C4→R1,
  C5→R5; C6 covered by R1's clause + P1 parked; R parked).
- **LOG:** PASS.
