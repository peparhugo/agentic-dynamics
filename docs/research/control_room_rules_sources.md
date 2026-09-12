---
status: accepted
---

# Control Room rules — pinned sources (d0 freeze)

**Status:** frozen. This file is the pin table for the published mandate that the Control Room
design is built against. Phase `d0_pin_sources` of
`workflows/repository/control_room_rules_design.yaml` fetches each URL once, stores the raw
record under `experiments/control_room_rules/sources/`, and fixes its `sha256`. **No later phase
may read the live web or make a claim from memory**; downstream phases cite only the frozen
records named here.

## Exact commands

Run from the repo root (`/tmp/control_room_research_wt`):

```bash
mkdir -p experiments/control_room_rules/sources
python3 scripts/research_fetch.py --out-dir experiments/control_room_rules \
  https://ai-finops-rulebook.web.app/framework.html \
  https://ai-finops-rulebook.web.app/evidence.html \
  https://ai-finops-rulebook.web.app/methodology.html \
  https://ai-finops-rulebook.web.app/index.html
```

`research_fetch.py` writes one immutable JSON record per distinct content hash to
`sources/<sha256[:16]>.json` (fields: `uri`, `final_url`, `status`, `content_type`, `sha256`,
`title`, `text`, `bytes`, `fetched_at`) and appends one line per stored source to
`sources.jsonl` (the append-only catalog). A content hash already present is a no-op. All four
URLs returned HTTP 200 with no redirect (`final_url == uri`); all four were newly stored.

## Pin table

| # | uri | final_url | fetched_at (UTC) | sha256 | title | extraction quality |
|---|-----|-----------|------------------|--------|-------|--------------------|
| 1 | https://ai-finops-rulebook.web.app/framework.html | …/framework.html | 2026-09-11T16:01:59.020337+00:00 | `30370e379a32ffcd8c80b27d34a3f386ae7ca5c6bd5806a9354b1f814d26c457` | Operational Framework — Agentic Dynamics | **full** |
| 2 | https://ai-finops-rulebook.web.app/evidence.html | …/evidence.html | 2026-09-11T16:01:59.169328+00:00 | `aa676d570db807c4b2162269f82c0d6a283b06f7daaf4e39e6dd29271dd1ad2d` | The Evidence — Agentic Dynamics | **full** |
| 3 | https://ai-finops-rulebook.web.app/methodology.html | …/methodology.html | 2026-09-11T16:01:59.765218+00:00 | `3bc3039b19ea19bcd2baa9739268e85a574fd88d8ce6e56d5ab1b73e71962360` | The Instrument — Agentic Dynamics | **full** |
| 4 | https://ai-finops-rulebook.web.app/index.html | …/index.html | 2026-09-11T16:01:59.992492+00:00 | `805d756a5f891ff03d153b283437f908ee9cbb911ebcdbcd648ab13869a2bf09` | Agentic Dynamics — No Universal Best Practices | **full** |

Stored record paths (repo-relative):

| # | record path | bytes (raw) | extracted text (chars) | text/raw |
|---|-------------|-------------|------------------------|----------|
| 1 | `experiments/control_room_rules/sources/30370e379a32ffcd.json` | 138,317 | 29,702 | 0.215 |
| 2 | `experiments/control_room_rules/sources/aa676d570db807c4.json` | 184,590 | 56,879 | 0.308 |
| 3 | `experiments/control_room_rules/sources/3bc3039b19ea19bc.json` | 46,236 | 24,855 | 0.538 |
| 4 | `experiments/control_room_rules/sources/805d756a5f891ff0.json` | 25,392 | 7,513 | 0.296 |

All four `content_type` values are `text/html; charset=utf-8` (a server-rendered static site),
so the stdlib text extractor recovered headings **and** body copy; no page is JS-rendered or
thin.

## Extraction-quality rubric

Adapted from the pinned-step convention in `workflows/repository/herdr_inspired_ux.yaml`
(`extraction_quality != "thin"`). A record is classified by re-reading its own frozen `text`
field:

| quality | test |
|---------|------|
| **full** | the text contains the page's required content anchors (rule statuses / engine stages / evidence classes) and the extracted text is substantial (≥ 5,000 chars) |
| **partial** | the page renders, but at least one required content anchor is absent from `text` |
| **thin** | the extractor recovered only chrome/navigation (`< 1,000` chars) or an empty title |

| # | required content anchor (present in frozen `text`) | quality |
|---|----------------------------------------------------|---------|
| 1 | `Ten rules, three statuses` + `01 / DECLARE Cell` … `05 / RECORD Ledger` | full |
| 2 | `cap_2b` randomized verdict + `Grit = Ground-Truth Integrity` + escalation `E_x` | full |
| 3 | `Perturbation Operators` + `[M]/[C]/[H]/[X]` provenance legend + cost drivers | full |
| 4 | `1,067` story sessions + `N — linked sessions` / `M — measurement angles` | full |

## Frozen-record contract (for d1–d5)

- The **only** evidence base is `experiments/control_room_rules/sources/*.json` (raw `text`
  fields) plus `sources.jsonl`. `docs/research/control_room_rules.md` is the derived verbatim
  extract that downstream phases quote.
- A claim whose source text is not in these records is a **gap**, not an assumption (hard rule
  3 of the spec).
- The `sha256` values above are the citation keys used throughout
  `docs/research/control_room_rules.md`.
