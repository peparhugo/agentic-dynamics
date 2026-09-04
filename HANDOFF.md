# HANDOFF — session 2026-09-04 (pick-up surface)

**Open with:** `python3 scripts/session_open.py` — the session spine (loop 2) works and
retrieves the last session's close. The campaign (Waves 1-4 + self-knowledge layer) is
fully merged to main at `8d4ee6202` (+ deep-review fixes `bcb54e260`, pushed).

## The state that matters

- **All machinery merged + verified**: the ONE engine (honest gates, false-green guard on
  main), the control db (9 merged/4 cancelled/8 failed — truthful), the control packet
  (clean, 0 phantom safe_actions), the authoring product (schema/linter/examples/new-lint-
  plan), the AIO agent (`.opencode/agents/aio-control.md`), the launch broker (systemd
  unit ACTIVE), and the self-knowledge layer (session spine round-trips live).
- **321 knowledge tests green** on the merged fixes.

## The ONE open thread: the finding-layer content fix needs its chroma re-index verified

The deep review found the KB's finding records were shells ("verdict not", no conclusions).
**Fixed + committed + pushed (`bcb54e260`):**
- F1: verdicts render as `not-merge-ready` (readable label), not bare `not`
- F2: conclusions + residuals now ride the retrieval `text` (backfill re-emitted 144 records)
- F3: session records carry prose summaries (findable by meaning, not just id)

**The catch:** the retrieval surface (chroma) still shows pre-fix content because the chroma
projection was frozen behind a stale-consumer/orphaned-event backlog since **Aug 17**.

**Projection cleanup — done:**
- Deleted 34 dead consumers (chroma + registry groups)
- Registry fully drained: lag=0, pending=0 (1931 entries processed `ok`)
- Acked ~200 chroma events whose artifacts no longer exist (superseded orphans)
- **Reset the chroma group to the stream head** (`xgroup_setid` to the last id) — the
  Aug 17-Sep 3 dead history is unrecoverable (artifacts purged; content superseded)

**What remains (small):**
1. Verify the chroma group now indexes FRESH events (emit one valid finding event →
   run `python3 scripts/kb_worker.py --group kb-chroma-v1 --once` → probe retrieval).
   The backfill's emit path is `python3 scripts/kb_backfill_findings.py` (all 167 waves
   already emitted — `already_present=1` — so a fresh event needs either a new wave record
   or a direct `publish_event` with the artifact's real `knowledge_id`/`content_hash`).
2. Then re-run the retrieval probe (`default_retrieve_fn()` on a wave question) to confirm
   `not-merge-ready` + conclusions surface — the F1/F2 fix made visible.

## Notes for the new session

- **Route merges through `workflow promote`** (not raw git) so the control db transitions
  stay truthful — the AIO's recorded lesson from this session.
- The kb_worker daemon running is `kb-neo4j-v1` only; chroma/registry workers are
  on-demand (`--once` or daemonize).
- Redis: framework queue on 6380; KB streams in db2 (`kb:v1:changes`).
- The k2 backfill shells (`findings 0, residuals 0, conclusion:""` for waves whose review
  docs use non-standard verdict phrasing) are a residual — the extractor captures structure
  but some waves' conclusions need the doc-format pass (kb_finding_layer adversarial F1).
- Optional queued: self_knowledge_layer task-card spec is DONE (it WAS the last wave);
  the authoring schema's `deliverable/inputs/done_when` task-card extension is still open.
