# Canonical-State Design — Verification

Verify phase of `experiments/specs/canonical_state_design.yaml`. Checks
`docs/canonical_state_design.md` against the spec's `forensic_findings`, `open_questions`,
and `design_priorities` before the design is pulled. Method: for every check below, I re-read
the actual design text (not my memory of writing it) and, where a claim depends on a specific
string appearing in the document, I grepped for it rather than asserting from recall — three of
the five gaps found below were caught exactly that way (see the grep results cited inline).

Verdicts use **PASS** / **PARTIAL** / **FAIL**, not a forced binary, because two of the six
forensic findings are genuinely half-addressed (a real recurrence-prevention mechanism exists,
but the concrete remediation-of-past-instances step is missing from the migration plan) and
collapsing that into PASS or FAIL would misrepresent the actual state of the design.

---

## 1. Forensic-findings traceability

Requirement: trace every `forensic_findings` item to a concrete mechanism — which store /
spine / surfacing step makes that corruption impossible to repeat.

| # | Finding | Mechanism cited in design.md | Verdict |
|---|---|---|---|
| 1 | ~59 re-run story results stranded in `feature/remediation-integrity` / `feature/queue-steer-2` (relative-path write) | OQ1's worktree-independent identity scheme (`entity_id` hashes a *logical* `source_uri = f"story:{story_id}"`, never a filesystem path) + Migration step 5 (explicit backfill pass pointed at both worktrees, with a named conflict-resolution rule for content mismatches) | **PASS** — see caveat below |
| 2 | `_results_summary.json` shrank 227→144; the 227-entry version is recoverable from git but has stale manifold/semantic labels and cross-matched baselines | OQ4/Migration step 4's decoupling principle ("is this canonical" no longer depends on "has the analysis pipeline caught up") prevents this **class** of loss recurring. But grepping the design for `227`, `git show`, `git-recover`, or `recoverable` returns **zero matches** — the migration plan never adds a step to actually recover the git-historical 227-entry blob and register its extra ~83 entries (as tombstoned-with-caveat, since their source worktrees are deleted and the labels are known-stale). The *recurrence-prevention* half is real; the *remediate-the-already-lost-83* half is missing. | **PARTIAL** |
| 3 | 2026-08-17 single-task results (7 models + 3 resamples) complete but not folded into `_results_summary.json` | Migration step 4, explicit and named — registers these results directly as canonical, independent of whether `analyze_worktrees.py` ever re-runs | **PASS** |
| 4 | `claude-fable-5` single-task runs (claude_cli backend) have no `opencode.db` session row; `analyze_worktrees.py:1098` silently drops them | `ledger_ingestion.py`'s documented signature is `derive_ledger_records(story_result, opencode_session_row, summary_entry, *, repository_id, now=None)` (design.md:262) — a **required** `opencode_session_row` parameter with no described fallback. Grepping the design for `opencode_session_row`, `claude_cli`, `no-session`, or `no session` finds the signature itself and nothing else — no branch is specified for the exact case finding 4 describes (a story/attempt with a story JSON but *no* matching DB row). The design's general "decouple from `_results_summary.json`" argument does not cover this, because the gap here is a **join input**, not a derived-view staleness issue. | **FAIL** |
| 5 | 52 `meta_*` analysis sessions can pollute `analyze_worktrees.py`'s worktree classification (`meta_batch_*` false-matches the "batch" title filter) | Grepping the design for `meta_` or `pollut` returns **zero matches**. Finding 5 is never named or traced anywhere in `docs/canonical_state_design.md`. A plausible mitigation is *implicit* in the architecture (every registered entity is individually inspectable via `scripts/registry.py show <id>` and individually tombstonable with a reason, versus today's silent, invisible bias to aggregate stats) — but "a plausible implicit mitigation exists" is not "traced to a concrete mechanism," which is what the requirement asks for. | **FAIL** |
| 6 | No date spine anywhere — only mtime + git history + Redis queue status distinguish canonical from stale | The entire OQ2 section (`observed_at`/`indexed_at`/`valid_from`/`valid_to`/`supersedes`/`lifecycle_state`) plus OQ3's CLI/Control Room surfacing directly replaces mtime/git-archaeology as the freshness signal for every record type in OQ1's table | **PASS** |

**Finding 1 caveat (does not change the PASS verdict, but is a real residual gap):** the identity
scheme guarantees that *if* a stranded file is eventually discovered and registered, it converges
to the correct entity rather than becoming a silent duplicate or being lost again. It does **not**
specify an ongoing discovery trigger — nothing in the design walks `git worktree list` or
otherwise proactively finds *future* stranded files; Migration step 5 only registers the two
worktrees already named by this forensic investigation. The corruption this finding describes
(data becoming *permanently unattributable*) is structurally prevented; the *time-to-discovery*
for a future instance of the same write-path bug is not bounded by anything in this design.
Recommend, as a follow-on: either have `save_story_result()` synchronously emit its own
registration event (write-time registration, not batch backfill), or have a periodic sweep
(`inventory.py refresh` or a new cron) walk `git worktree list` output for story JSONs the
registry hasn't seen yet.

---

## 2. Open questions answered with a schema/sketch (not prose)

| OQ | Topic | Schema/sketch present? | Verdict |
|---|---|---|---|
| 1 | Registry model, record fields, identity key | Python dataclass diff (`supersedes` field with docstring), a 6-row `source_type`/authority table, a 6-row identity-formula table, and the exact `entity_id`/`knowledge_id` hash formulas | **PASS** |
| 2 | Date-spine fields + supersession semantics | Field-by-field definitions tied to the existing `KnowledgeEvent.operation` enum (`upsert`/`supersede`/`delete`), plus two new named edge types (`CLEARED_BY`, `REPLACED_BY`) with explicit semantics | **PASS** — structured as definitions reusing an existing enum rather than a fresh table, but every claim is concrete (specific field names, specific enum values, specific edge names), not prose hand-waving |
| 3 | The ONE surfacing CLI + Control Room board | `scripts/registry.py show/query/lineage` command sketch with argument shapes, plus `GET /api/registry` / `GET /api/registry/<entity_id>` route sketch styled on the existing `/api/flags` envelope | **PASS** |
| 4 | Store split (files / Neo4j / parquet / manifest) | 4-row table, one row per layer, explicit "yes, the manifest is the registry index" answer | **PASS** |
| 5 | KB extension — new record_types through existing ingestion | 4 producer-module code blocks with function signatures, `EXTRACTOR_VERSION` constants, and an explicit new consumer group (`kb-registry-v1`) | **PASS** |
| 6 | Supervisor's three layers as durable records | Concrete identity formulas (reused from OQ1's table) and concrete function/edge names (`ledger_ingestion.py`, `CLEARED_BY`) are present, but layers (a)/(b)/(c) are explained as paragraphs rather than a dedicated schema table the way OQ1/OQ4/OQ5 are | **PASS**, weakest of the six — recommend a follow-up table (verdict / monitor_session / flag × fields × identity × authority) consolidating what's currently spread across OQ1's table and OQ6's prose |

---

## 3. Backward compatibility

Requirement: no existing result JSON is rewritten; records are registered, not re-factored.

- Both new dataclass fields (`KnowledgeRecord.supersedes`, `KnowledgeEvent.reason`) are appended
  **after** the existing trailing-default fields (`confidence`/`perturbation_strength` on
  `KnowledgeRecord`, `event_id` on `KnowledgeEvent`), which is the only place Python dataclass
  field ordering allows a new defaulted field to go without breaking the class definition or any
  existing positional construction. I checked this against the actual field order in
  `src/instrument/knowledge.py` rather than assuming it — the ordering is valid.
- `story`/`review`/`flag` record types are explicitly pointer-only (`source_uri` targets the
  pre-existing file; "no copy is written" / "no duplicated body" stated directly in the design).
- The manifest's existing `files{}` block is explicitly kept unchanged; the registry becomes a
  new, additive `registry` array alongside it.
- The Scope Boundary section restates this as an explicit bullet ("No rewriting or relocation of
  any existing story/review/result JSON").

**Verdict: PASS.** No counter-example found anywhere in the design.

---

## 4. Supervisor stays observe-only (flag-only rail)

Requirement: verdicts, monitor session, and flags become durable records without gaining any
steering authority; the monitor session's own cost/tokens are measured by the same instrument
(not free observation).

- **Verdict → `observation` record**: every assessment is registered (not just non-`healthy`
  ones, closing today's audit gap), `authority=ADVISORY`, `evidence_class="[H]"` — a passive
  data write, no session-control call anywhere in its description.
- **Monitor session cost → reuses `ledger_ingestion.py` directly**, pointed at the monitor's own
  `session_id` (read from `monitor_session.json`), tagged with a synthetic `cell_id` so it sorts
  distinctly. This is the literal, explicit answer to "measured by the same instrument" — same
  function, same record type as any other attempt, not a bespoke exemption.
- **Flag supersession + clearance**: flags get a `supersedes` chain per `session_id` (matching
  the existing "newest wins" UI rule, now durable). Clearance is **fully automatic**: a
  `kb-registry-v1` consumer rule ("healthy observation for a session with an untombstoned flag →
  emit a `delete` for that flag"). This logic lives in the **KB stream consumer**, not in
  `scripts/supervise.py` itself — the supervisor process's own code is unchanged except for
  calling two producer functions (observation, and the reused ledger producer). I checked this
  distinction specifically because it's the part most likely to accidentally cross the
  observe/control boundary if implemented carelessly (e.g., if the clearing logic lived inside
  the supervisor's own poll loop and someone later "enhanced" it to also nudge the session) — as
  designed, the clearing logic has no path to `OpenCodeClient` at all, since the KB consumer
  process doesn't import it.
- **Zero new mutating Control Room routes.** The design explicitly declined to add a human
  "clear this flag" button (Scope Boundary), which is the more conservative choice and further
  reduces the surface that could later be extended into steering.
- Grepped the whole design for `send_input` and `interrupt`: both appear only in the sentence
  explicitly confirming neither is called by anything new.

**Verdict: PASS.** This is the most carefully argued part of the design, and it holds up under
a skeptical re-read — I looked specifically for a place where "durable record" quietly implies
"and also nudge the session" and did not find one.

---

## 5. Additional check: does the design's OQ4 Neo4j promise actually get built?

Not explicitly asked for by the phase's requirement list, but worth flagging because it's a
concrete, checkable gap the same grep-first method surfaced: OQ4's table promises Neo4j
`Knowledge` nodes gain `supersedes`/derived `lifecycle_state` properties, and OQ2 says the
*effective* `valid_to` is computed and written into "the index layers (Neo4j node property,
the manifest's `registry` array, `registry_index.jsonl`)." But the inventory phase already
found (`docs/canonical_state_inventory.md`, store #12) that `kb_worker.py`'s existing
`kb-neo4j-v1` `SET` clause **already drops** `valid_from`/`valid_to`/`indexed_at` for the four
record types that exist today. The design's Migration plan (step 1: schema additions; step 2:
new producers + the new `kb-registry-v1` consumer) never lists "extend `kb-neo4j-v1`'s Cypher
`SET` clause to actually persist `supersedes`/`lifecycle_state`/`valid_from`/`observed_at`" as a
step. Without that, OQ4's Neo4j promise is not achievable by the migration plan as written — the
new fields would suffer exactly the same silent drop the inventory phase already documented for
the existing ones.

**Verdict: PARTIAL** (folds into OQ4's PASS above as a completeness caveat, not a separate
open-question failure, since OQ4's *design* answer is correct — the *migration plan* just
doesn't yet implement it).

---

## Summary

| Check | Verdict |
|---|---|
| Finding 1 — stranding | PASS (residual: no proactive future-discovery trigger) |
| Finding 2 — `_results_summary.json` staleness | PARTIAL (recurrence prevented; past 83 entries not remediated) |
| Finding 3 — un-folded single-task results | PASS |
| Finding 4 — no-session (claude_cli backend) | **FAIL** |
| Finding 5 — meta_* pollution | **FAIL** |
| Finding 6 — no date spine | PASS |
| OQ1 registry + identity | PASS |
| OQ2 date spine + supersession | PASS |
| OQ3 surfacing (CLI + Control Room) | PASS |
| OQ4 store split | PASS (migration plan incomplete for Neo4j — see §5) |
| OQ5 KB extension | PASS |
| OQ6 supervisor's three layers | PASS (weakest schema density of the six) |
| Backward compatibility | PASS |
| Supervisor observe-only / flag-only rail | PASS |

**Overall: not clean — 2 of 6 forensic findings (4, 5) are not yet traced to a concrete
mechanism, and 1 more (2) has its recurrence-prevention half done but its remediation-of-past-
loss half missing.** Everything else — the registry model, the date spine, the surfacing paths,
backward compatibility, and (most importantly, given the risk) the supervisor's observe-only
guarantee — holds up under a skeptical re-read.

### Before this design is pulled, recommend closing:

1. **Finding 4** — give `ledger_ingestion.py` an explicit fallback branch for when
   `opencode_session_row` is `None` (claude_cli-backend runs): read tokens/cost directly from
   the story JSON's `sessions[].agentic` block (already present per the inventory phase's sample)
   or from `claude_adapter.py`'s own `AgenticResult`, rather than requiring the DB join to
   succeed.
2. **Finding 5** — add an explicit paragraph naming `meta_*`/`meta_batch_*` sessions and stating
   the mechanism (individually-inspectable, individually-tombstonable registration replacing
   today's silent aggregate-stat pollution), plus a migration note to audit and tombstone any
   `meta_*` entries that already leaked into `_results_summary.json`.
3. **Finding 2** — add a migration step that runs `git show <pre-shrink commit>:experiments/
   results/_results_summary.json`, diffs it against the current 144 entries, and registers the
   extra ~83 as `upsert` records with `evidence_class` downgraded or a `reason`-bearing caveat
   noting the known-stale manifold/semantic labels and cross-matched baselines — tombstoned only
   if a clean replacement exists, otherwise registered as a caveated-but-canonical historical
   record (the source worktree is gone; this is the best available fact, not a fiction).
4. **OQ4/Neo4j** — add "extend `kb-neo4j-v1`'s `SET` clause to persist `supersedes`/
   `lifecycle_state`/`valid_from`/`observed_at`" to Migration step 1 or 2, since the design's own
   OQ4 answer depends on it and the inventory phase already proved the current handler drops
   these fields silently.
