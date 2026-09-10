---
status: accepted
---

# AIO controller postmortem — defense-gap matrix (p2)

**Inputs:** `docs/reviews/aio_controller_postmortem_taxonomy.md` (p1, commit `85102565d`) —
classes C1–C6 + Rare; `docs/reviews/aio_controller_postmortem_corpus.md` (p0, commit
`d19ef95a9`) — items F-01…F-19.
**Role:** inventory the CURRENT defenses, map each taxonomy class to the defense(s) that
*should* catch it, mark **catches / partially catches / does not exist**, and name a minimal
remediation candidate for every class that no current defense catches.
**Constraint honored:** candidates prefer **rule text in `agent_config/rules.md`**; an
**existing rail extended** is second; a **new mechanism** is named only with a
justification and is a p3 decision, not made here.

---

## 1. Current defense inventory (what exists, and what it actually asserts)

Trigger vocabulary: **CI** (push/PR), **commit** (commit-time / phase-boundary),
**on-demand**, **nightly** (scheduled), **flag-only** (observes, never steers).

### 1a. Rules doctrine — `agent_config/rules.md` (rendered to `AGENTS.md`/`CLAUDE.md`)
All of it is **prose**: it directs, it does not enforce.

| Clause | Quote (abridged) | Lines | Speaks to |
|---|---|---|---|
| Permanence gate | "Merging a worktree branch into `main` … is … controller alone … says so and stops; it does not do it." | 42–45 | C1, C3, C6 |
| Verified commands | the AIO "routes every permanence verb through the verified commands (`promote.py`, `publish release`), and never bypasses the gates." | 29–31 | C2, C3 |
| Generated surfaces | "Never hand-edit a generated file … CI runs it on every push, so a source edited without regenerating is a red build rather than silent drift." | 20 | C3 |
| Recording discipline | "a session that does not write its close record has not closed." | 35–39 | C4, C6 |
| Observe-only | "supervisor and the lease watchdog raise FLAGS … they never kill, re-route, or edit a run." | 50–52 | C5 (boundary), C6 |
| One writer per plane | "children never write the outbox … Per-projection watermarks are the single documented exception." | 53–55 | C4 |
| Lease/unknown cost | "no lease, no spend, and an unknown cost is never treated as zero." | 46–49 | C1 (spend), C5 |
| Redis isolation | "Never run the queue on 6379." | 118 | C1 (destructive store) |

**Rule-text gap:** there is **no clause** about destructive durable-store/repo operations
(C1) and **no clause** about authoring a parallel mechanism (C2). The nearest is D2
("never bypasses the gates"), advisory only.

### 1b. Skills — `.opencode/skills/*/SKILL.md` (prose)
- `run-workflow` — phase gates are "spec markers, not flags"; **"Do not invent a script
  wrapper for it; none exists"** (≈195–199); orchestrator-first, in-process fallback.
- `queue` — Redis isolation (13–16); `--clear` is destructive, "never auto-run it" (104–105).
- `control-room` — GET-only, no steering POSTs (11–20).
- `instrument` / `analyze` / `lab-books` / `review` — single-source-of-truth and ordering
  directives; `analyze` "`data.js` is generated — never edit directly".

### 1c. Verified commands / phase gates (code)
| Rail | Asserts | Trigger | Pointer |
|---|---|---|---|
| `promote.py` identity | candidate HEAD == ledger `git_sha`; refuse rewritten candidates | on-demand | `scripts/promote.py:463-471` |
| `promote.py` evidence | every phase ok; every test phase `test_executed_success is True`; commit_hash present | on-demand | `scripts/promote.py:477-496` |
| `promote.py` approval | approval binds the candidate sha + real operator + date | on-demand | `scripts/promote.py:647-668` |
| `promote.py` stale-tree refusal | candidate tree already on base ⇒ refuse + cancel the row | on-demand | `scripts/promote.py:758-791` |
| `promote.py` row close | `promotable→promoting→merged` + `promotions` row (best-effort, after push) | on-demand | `scripts/promote.py:295-411` |
| Workflow deploy gate | firebase prod deploy without `deploy_allowed` fails `DEPLOY_GATE` | commit | `workflow_runner.py:1611-1643` |
| Commit-prefix gate | every phase commit matches `[workflow] <phase> — <goal prefix>` | commit | `workflow_runner.py:1947-2120` |
| NO_CHANGES gate | a `requires_deliverable` phase must change the tree | commit | `workflow_runner.py:1994-2039` |
| Relabel tree-identity | a discarded tree re-presented fails `RELABEL` unless operator-signed reuse | commit | `workflow_runner.py:2395-2457` |
| Checkpoint gate | a `checkpoint: true` phase stops; resume needs a signed post-work approval | commit/on-demand | `workflow_runner.py:2614-2681` |
| `record_discarded_tree.py` | records the discarded tree (flag-only) | on-demand | `scripts/record_discarded_tree.py:43,53-71` |

### 1d. Control packet + control DB
- `control-status/v1` self-validates; `safe_actions` are derived from
  `ALLOWED_TRANSITIONS` so the packet can only offer db-legal actions
  (`control_status.py:447-524`); the DB opens read-only for observers
  (`control_db.py:1220-1273`).
- SQLite **append-only triggers** cover `runs/step_attempts/gate_results/approvals/
  promotions/run_transitions` (`control_db.py:1058-1113`).
- **No data-volume/direction assertion** and **no worktree-vs-main runtime gate** anywhere;
  `check_branch_protection.py` is a **release-time/on-demand** drift check only.

### 1e. Recording rail + session spine
| Rail | Asserts / does | Trigger | Pointer |
|---|---|---|---|
| `session_close.py` | writes the close + reflection append; **best-effort**, shape-only | on-demand | `scripts/session_close.py:181-233` |
| `decision_record.py` | records a decision; **best-effort**, shape-only | on-demand | `scripts/decision_record.py:141-186` |
| KB write guard | refuses a publish without `FINOPS_KB_WRITE=1`/`authorized` — *whether*, not *who* | at call time | `knowledge_stream.py:198-201` |
| `recording_sweep.py` | commit-days with no decision AND no close = gap; **phantom-claim** detector; `--backfill` (actor `recording-sweep`) | **nightly + on-demand** | `scripts/recording_sweep.py:103-137,144-186` |
| session `close_seq` | same-day closes ordered by close-order (not slug) | write/read | `session_ingestion.py:574-635` |
| `open_session` | last close resolved by direct durable-read (no registry projection) | on-demand | `session_ingestion.py:669-726` |
| reflection series | one current entry per session, ordered | write/read | `reflection_ingestion.py:292-401,537-632` |
| supervisor / lease_watchdog / quarantine / orphan_sweep | flags + quarantine marks; **flag-only** | flag-only | `control/supervisor.py:1-6`; `lease_watchdog.py:10`; `orphan_sweep.py:1` |

> **Timer note (verified at mining time):** commit `f7d9ebe42` claims a "nightly timer" but
> the repo commits **no timer unit**. A host **systemd user unit**
> `agentic-dynamics-recording-sweep.timer` **is installed and live** (next run 03:47 CEST),
> so the rail does run nightly on this machine — but it is not provisioned from repo source
> (blast-radius/reproducibility gap). Treated as **nightly** below.

### 1f. Automated guards (tests / CI)
| Guard | Asserts | Trigger | Pointer |
|---|---|---|---|
| Generated surfaces | rendered `AGENTS.md`/`CLAUDE.md`/`.opencode`/`.claude` == source render (stale/missing/orphan) | **CI** | `_gen_instructions.py:483,564`; `tests/test_agent_config_render.py:298-373` |
| Fast-path gate | fast path < 180 s; `fast` modules pass the parallel-safety audit | **CI** | `tests/test_fast_path_gate.py:26,32-113` |
| Doc lifecycle | every doc has a `status`; kind-tree statuses; **README spec-count == `experiments/specs/index.json`** | **CI** | `tests/test_doc_lifecycle.py:66,79,91,123,245-255` |
| Docs drift | 7 axes re-derived (`spec_lifecycle`, `manifest_counts`, `fast_path`, …); reports, `--fail-on-drift` | hourly (repo timer) / on-demand | `scripts/scan_docs_drift.py:43-56,106-113` |
| Dependency direction | import-tier rules; pinned telemetry seam | **CI** | `tests/test_dependency_direction.py:39-55` |
| Data flow | retrieval never publishes; `knowledge/` never actuates | **CI** | `tests/test_data_flow.py:29,35,57-70` |
| Script classification | every `scripts/**/*.py` in exactly one manifest bucket; `maintained` scripts CLI-reachable | **CI** | `tests/test_script_classification.py:49-77` |

**"Would it catch…" quick matrix:** README drift → YES (doc lifecycle); a new loose
`scripts/*.py` → YES (classification); a registry merge that deletes rows → **NO**; a new
YAML agent-spec wrapper → **NO**.

---

## 2. The defense-gap matrix (the deliverable)

Legend: **catches** = an enforced rail asserts the class's invariant and would fail/block;
**partial** = a rail exists but its predicate is weaker, or it only observes/reports;
**none** = no rail asserts it.

### C1 — Destructive durable-store/repo operation without the documented convention
| Defense that should catch it | Verdict | Why it does not |
|---|---|---|
| `promote.py` (identity / evidence / stale-tree) | **none** | It validates *tree identity and provenance*, never a **data-volume or direction delta**; the drain merge (`9e4773fb1`) deleted 43,311 registry rows and passed. |
| "machine state" commit convention | **none** | Sweeps derived state, does not inspect what a sweep removes. |
| SQLite append-only triggers | **partial** | Protect the control tables (`control_db.py:1058-1113`) but **not** `registry_index.jsonl`. |
| Rule text (`rules.md`) | **none** | No clause names destructive store/repo ops or their conventions. |
| `test_script_classification` / data-flow guards | **none** | Not about data deltas. |
| **Class verdict** | **does not exist** | — |
| **Remediation candidate (for p3)** | **Rule text (preferred):** add a directive — *"Before any bulk mutation of a durable store or the git index/refs (merge, dedup, `add -A`, `rm --cached`, history rewrite), apply the store's documented convention and prove the volume/direction is safe: append-only ⇒ union merge, never take a side; dedup ⇒ full-row equality only; ignore-before-add. A write that shrinks an append-only store is a violation."* **Optional rail extension (second):** a pre-commit/CI assertion that a tracked append-only store (`registry_index.jsonl`) never loses lines relative to its merge base. A new mechanism is not justified while the rule + this one assertion suffice. |

### C2 — Mechanism improvisation / over-building when the documented path is unsatisfying
| Defense that should catch it | Verdict | Why it does not |
|---|---|---|
| `rules.md` verified-commands doctrine | **partial** | Prose only; "never bypasses the gates" names gates, not mechanism creation. |
| `run-workflow` skill ("do not invent a script wrapper") | **partial** | Prose only; no gate. |
| `test_script_classification.py` | **partial** | Catches a new loose `scripts/*.py` (orphan) — but **not** a new YAML agent-spec wrapper; and the launcher was deleted before CI saw it. |
| `test_experiment_workflow_classification.py` | **none** | Only checks `artifact_kind` matches its directory; `recording_sweep.yaml` passes. |
| Workflow-v1 linter/schema | **none** | Lint only workflow-v1 / `examples/`; the ExperimentSpec corpus is excluded (`test_workflow_examples.py:224-231`). |
| **Class verdict** | **partially catches** (new `.py` mechanisms only) | — |
| **Remediation candidate (for p3)** | **Rule text (preferred):** *"When a documented path fails, stop and record the gap; do not author a parallel mechanism. A net-new top-level mechanism (script or agent-spec wrapper) requires a named justification and goes through the authoring surface."* **Rail extension (second):** require a `mechanism:`/justification field (or an authoring-surface review) for a net-new top-level `scripts/*` mechanism **or** a corpus agent-spec wrapper. |

### C3 — Documented-convention miss (a rail exists; it is not followed)
| Defense that should catch it | Verdict | Why it does not |
|---|---|---|
| Generated-surface CI check | **catches** (instruction surfaces) | Byte-equality for `AGENTS.md`/`.claude`/`.opencode`; does **not** cover `README.md`/`index.json`. |
| `test_doc_lifecycle.py` README assertion | **catches** (spec count) | Now asserts README row == `experiments/specs/index.json` — F-19 fails CI today. |
| `scan_docs_drift.py` | **partial** | Re-derives 7 axes but **reports** (hourly, not in `pytest.yml`); `--fail-on-drift` is opt-in. |
| Permanence gate prose (worktree vs main) | **partial** | No runtime gate; `check_branch_protection.py` is release-time/on-demand; direct-`main` commits pass. |
| Skills (command shapes) | **partial** | Prose only; the wrong-script runs were ad-hoc. |
| **Class verdict** | **partially catches** | Generated surfaces + README are enforced; direct-`main`/permanence and command-shape misses are not. |
| **Remediation candidate (for p3)** | **Rule text (preferred):** make the worktree/promote shape directive for anything beyond a small derived-surface sweep, and bind it to the permanence gate. **Rail extension (second):** move the docs-drift `spec_lifecycle`/`manifest_counts` axes into CI (`--fail-on-drift`) so generated-surface drift is a red build, not an hourly report. |

### C4 — Record-layer integrity gap (missing / phantom / stale / mis-ordered / unattributable)
| Defense that should catch it | Verdict | Why it does not |
|---|---|---|
| `recording_sweep.py` gap + phantom detector | **catches** (missing & phantom) | Detects commit-days with no decision/close, flags phantom `decision record <id>` citations, and backfills; **nightly (host timer) + on-demand**. Does not validate attribution, staleness, or currency. |
| `session_close.py` / `decision_record.py` | **partial** | Best-effort, shape-only; no write-time validity or attribution check. |
| KB write guard | **partial** | Guards *whether* a write happens, not *who* produced it. |
| session `close_seq` (fixed) | **catches** (ordering) | Now orders same-day closes by close-order. |
| `promote.py` row close (fixed) | **catches** (stale rows on promote) | Closes `promotable→merged` after push (best-effort); fixed in-window. |
| Control append-only triggers | **partial** | Immutability of terminal rows, not staleness/validity. |
| Zombie-row prevention | **none** | The runner creates a control row **before** validating the workdir (F-12). |
| **Class verdict** | **partially catches** | The largest class; missing/phantom/ordering are covered, attribution/staleness/zombie-minting are not. |
| **Remediation candidate (for p3)** | **Rule text (preferred):** *"Record at the moment of the act: a consequential act gets its decision record when decided, not in retrospect; a session closes or is explicitly parked."* **Rail extensions (second):** validate referents before minting/writing (a cited decision exists before a close lands; a run row is created only after the workdir validates); extend `recording_sweep` attribution checks to producer-path (the F-08 class). `promote.py`'s row-close is the precedent to copy. |

### C5 — Silent unreliable surface (a broken invariant/health state persists unobserved)
| Defense that should catch it | Verdict | Why it does not |
|---|---|---|
| Publication-contract CI test | **partial** | Asserts `data.js`↔manifest **identity**, not payload **resolution** (F-05). |
| Projection watermarks | **partial** | `null` ≠ `0` for stale/unknown lag (good), but lag is not provenance (F-17). |
| Worker heartbeat classification | **partial** | Classifies stale/no-heartbeat; had **no TTL**, so ghosts read as live (F-18). |
| supervisor / lease_watchdog / quarantine | **flag-only** | Correctly never steer; a flag is information, so a broken invariant needs a reader. |
| **Class verdict** | **partially catches** | Observability exists; the predicates are too weak and the rails only report. |
| **Remediation candidate (for p3)** | **Rail extension (preferred; existing rails suffice):** add a **resolution** assertion to the publication-contract test (every current registry row resolves or has a waiver/tombstone); assert a **corpus-mount/live-root** condition for corpus readers; make heartbeat-TTL an enforced invariant. No new mechanism. |

### C6 — Unbounded pursuit without checkpoint/close ("no exit ramp")
| Defense that should catch it | Verdict | Why it does not |
|---|---|---|
| Session-close doctrine prose | **none** | "a session that does not write its close record has not closed" is exactly right and is not enforced (F-01). |
| `checkpoint: true` phase gate | **catches** (inside a run) | Stops a run for a signed post-work approval (`workflow_runner.py:2614-2681`); does not cover interactive work. |
| Phase watchdog (`STALLED`) | **catches** (in-run stall) | SIGTERMs a transcript silent past the watchdog; not an interactive session. |
| `recording_sweep` missing-close detection | **partial** | Catches a missing close **after the fact**, not in-flight pursuit. |
| Single-writer prose | **none** | No gate; two sessions shared the main checkout (F-16). |
| **Class verdict** | **does not exist** (for interactive work) | — |
| **Remediation candidate (for p3)** | **Rule text (preferred):** *"Checkpoint or park before a task changes frame; never leave a shared checkout carrying a large uncommitted wave."* **Rail extension (second, flag-only):** extend the supervisor to flag (a) an interactive session idle/open past a threshold with no close, and (b) a shared checkout with uncommitted work above a threshold. Remains observe-only per D5. |

### R — Rare / environmental degradation (F-07)
| Defense that should catch it | Verdict | Why it does not |
|---|---|---|
| Machine-state churn sweep | **none** | It created the heavy tracked data plane; it does not measure snapshot/index cost. |
| opencode docs warning | **none** | External; no in-system metric. |
| Corpus migration + `snapshot:false` | **catches** (retroactively) | The window's fix retired the root condition. |
| **Class verdict** | **does not exist** (no in-system rail measured it) | — |
| **Remediation candidate (for p3)** | **Parked / no action:** the condition is fixed by the corpus migration (`ab887b5c8`) + `snapshot:false`; a new metric is not justified. If chosen, attach a working-set/snapshot-size line to an existing surface, not a new rail. |

---

## 3. Remediation-candidate summary (ranked by leverage → p3 input)

| Rank | Class | Candidate | Kind | Why this rank |
|---|---|---|---|---|
| 1 | **C4** (5 items, sev ≤3) | Record-at-the-moment rule + validate referents before minting (close citation, run row) | rule text + rail extension (`recording_sweep`, runner) | Largest class; cheapest leverage; `promote.py`'s row-close is a working precedent |
| 2 | **C1** (3 items, sev 5) | Bulk-mutation convention directive + one append-only volume/ordering assertion | rule text + one rail extension | Highest severity (F-03 data loss); one assertion closes the whole drain/dedup class |
| 3 | **C3** (3 items, sev ≤3) | Worktree/promote directive + move docs-drift axes into CI | rule text + rail extension | Generated-surface part already enforced; cheap to finish |
| 4 | **C2** (2 items, sev ≤2) | "Stop and record the gap" directive + justification for net-new mechanisms | rule text + rail extension | Prose already nearly right; close the wrapper loophole |
| 5 | **C5** (3 items, sev 4) | Resolution/mount/TTL assertions added to existing surfaces | rail extension only | Rails exist; weak predicates are the whole gap |
| 6 | **C6** (2 items, sev 4) | Checkpoint/park directive + flag-only open-session/uncommitted-work supervisor flag | rule text + rail extension (flag-only) | Highest impact on F-01, but the rail must stay observe-only per D5 |
| — | **R** | none (fixed by the corpus migration) | parked | no new mechanism justified |

---

## 4. Defense-audit completion log

- **DONE_WHEN — every class has a row with a catching/partial/none verdict:** PASS
  (C1 does-not-exist; C2 partial; C3 partial; C4 partial; C5 partial; C6 does-not-exist for
  interactive work; R does-not-exist — 7/7).
- **DONE_WHEN — a remediation candidate where none catches:** PASS (C1, C6, R carry
  candidates; C2–C5 carry strengthening candidates, flagged as such).
- **Constraint — rule text preferred, rail extension second, new mechanism only with
  justification:** PASS (no candidate proposes new machinery; every one is rule text or an
  existing-rail extension).
- **LOG:** PASS.
