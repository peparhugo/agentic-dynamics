# Control Room UI Redesign — Verification

> Phase: **verify** (`control_room_ui_redesign` spec, phase 3 of 3).
> Audits `docs/control_room_ui/design.md` (and its source, `docs/control_room_ui/research.md`)
> against three things: (1) the spec's `hard_rules`, (2) the actual `admin/server.py` routes +
> `admin/static` DOM + data shapes, and (3) the internal claim that every design decision is
> traceable to a research source. Each check below is PASS or FAIL, with evidence.

## 0. Method

- **Route audit**: extracted the route set from `admin/server.py`'s docstring (lines 5–41) and
  reconciled it against `design.md §1.2` / `research.md §0.1`.
- **DOM audit**: reconciled `design.md §1.3` migration map against the ids/classes in
  `admin/static/index.html`.
- **Data-shape audit**: reconciled `design.md`'s field references against `admin/server.py`
  (`api_matrix`, `_load_supervisor_flags`) and `docs/supervisor_design.md §4`.
- **Citation audit**: extracted every `[R §x.y]` in `design.md` and confirmed each target
  section exists in `research.md`; enumerated every `UNCITED` choice.

## 1. Check A — Every design decision traces to a research source

**Verdict: PASS** (with 3 disclosed + 1 audited minor uncited specifics; none is an aesthetic
judgment that affects grounding).

**Citation coverage.** The design makes 22 substantive decisions (§1 principles/IA/nav,
§2 fleet, §3 detail, §4 flags, §5 status, §6 sessions, §7 routing/system, §8 visual system).
All 22 carry an inline `[R §x.y]` citation. The citation targets resolve cleanly — the audit
found **zero dangling citations** (every cited section exists in `research.md`):

| Cited target | Used for |
|---|---|
| `[R §2.1]` Datadog host map / Grafana panel wall | fleet matrix + stage strip together |
| `[R §2.2]` GitHub/PagerDuty status language | two-axis status/attention color |
| `[R §2.3]` K8s/Lens, LangSmith | progressive disclosure, drill-down |
| `[R §2.4]` single-context handoff | one terminal, one EventSource |
| `[R §2.5]` PagerDuty/Better Uptime | Flags board + three states |
| `[R §2.6]` Material 3 AppBar | sticky command rail + bottom tabs |
| `[R §2.7]` Material 3/iOS sheets | bottom-sheet drill-down |
| `[R §2.8]` GitHub type-to-confirm | gated actuation |
| `[R §2.9]` PagerDuty dedup | calm under load |
| `[R §2.10]` Vercel/GitHub Actions logs | terminal surface |
| `[R §2.12]` GitHub PR sidebar | facts panel field order |
| `[R §1.x.y]` Linear, Geist, Stripe, Railway, Datadog, Netdata, Grafana, LangSmith, Material 3, Apple HIG | palette, spacing, typography, nav conventions |

**Uncited choices (enumerated).** The design self-discloses three; the audit found a fourth.
All four are *numeric implementation details*, not taste-based "looks nice" decisions:

1. `design.md §2.3` — the two density min-widths (`190px`/`150px`, `132px`/`84px` heights). **Disclosed.**
2. `design.md §3.2` — the "first three lines" glanceability target. **Disclosed.**
3. `design.md §8.4` — exact point sizes (11/12/13/14/16/24). **Disclosed.**
4. `design.md §1.4` — the collapsed left-rail width (`48–56px`). **Found by audit, not disclosed.**

Recommendation to the implementer: either cite an existing product's rail width (Datadog's
collapsed rail is 56px) or record these four as explicit `TODO(verify)` constants. None
changes the design's grounding.

## 2. Check B — Mobile is specified explicitly (one-handed)

**Verdict: PASS.**

The design specifies, not merely mentions, the one-handed layout:

- **Sticky bottom tab bar** for the five destinations, with the *cited* rationale for
  tabs-over-hamburger-drawer (`design.md §1.4`, Material 3 `NavigationBar` 3–5 destinations +
  Linear/PagerDuty mobile). This is an explicit, implementable navigation choice.
- **Modal bottom sheet** for every drill-down (`§1.5`, `§2.7`, `§3.1`), preserving the board's
  scroll position and docking primary actions at the bottom (thumb zone).
- **Reach spec**: the `follow` toggle is placed bottom-right (`§3.3`) and safe-area handling is
  named (`env(safe-area-inset-*)`, `§2.7`) — both iOS one-handed patterns (`[R §1.4.2]`).
- **Compaction chain**: card → list → table (`§1.2`/`§2.3`/`§7.1`, `[R §1.4.3]`), with a
  mobile wireframe per board (§2.1, §3.1, §4.1, §5.1, §6.1, §7.2) and a desktop/mobile nav
  sketch (§1.4).

This directly replaces the current anchor-jump stack the spec called out as broken.

## 3. Check C — Flag-only rail is visibly preserved

**Verdict: PASS.**

- The supervisor invariant is restated and honored: **"the supervisor flags; the human
  reviews, decides, and acts"** (`design.md §9`), and the read/act boundary is made explicit
  (§4.3, §3.4).
- The Flags board is **read-only by construction** — no list action sends a request
  (`§4.3`); Steer and Interrupt remain the *only* actuation, behind the existing deliberate
  Steer composer and the **type-to-confirm** `INTERRUPT <session_id>` door (`§3.4`, `[R §2.8]`).
- The "**Supervisor flags. You decide.**" copy stays visible on the board footer *and* above
  actions (`§4.3`), matching `docs/supervisor_design.md §1`'s deliberate repetition.
- Heuristic verdicts (`off_track`/`stalled`) are kept visually separate from lifecycle states
  via a two-axis color language (`§2.2`, `[R §2.2]`) — rose for `off_track` vs. red for
  `failed`, plus location + word redundancy so color is never the sole signal.
- Single-context handoff is preserved: exactly one global and one selected-detail
  `EventSource` (`§1.1`, `§3.3`, `[R §2.4]`), and Detach/Clear/refresh/unload never trigger an
  interrupt (`§3.4`).

## 4. Check D — Maps to the actual 28 routes + data shapes (no invented endpoints)

**Verdict: PASS** (with one correction to the research doc's route-count prose and one
under-specified facet, both recorded below — neither invents an endpoint).

**Route reconciliation (28/28).** The six destinations in `design.md §1.2` cover all 27 API
routes; the 28th (`GET /`) is the static shell serving every board and is correctly *not*
assigned to any single board:

| Destination | Routes | Count |
|---|---|---|
| Fleet | `GET /api/matrix`, `GET /api/status` | 2 |
| Status | `GET /api/matrix`, `GET /api/status` (shared with Fleet) | (shared) |
| Flags | `GET /api/flags`, `POST /api/flags/<id>/steer`, `POST /api/flags/<id>/interrupt` | 3 |
| Sessions | 7 design-session routes + 9 claude-agent routes | 16 |
| Routing | `GET /api/routing` | 1 |
| System | `GET /api/registry`, `GET /api/registry/<entity_id>`, `POST /api/experiments`, `POST /api/queue/reinterleave` | 4 |
| Detail | `GET /api/events/<cell_id>` (+ actuation routes on demand) | 1 |
| Shell | `GET /` | 1 |

**No invented endpoints.** The grep-audit confirms `design.md` references only the routes
above. `§9` states explicitly that the redesign is a re-skin/re-layout and "**No new route** is
required."

**Data-shape reconciliation.** Every field the design names exists in the current transport:

- `cells`, `phases`, `stages`, `telemetry{reported_cost, input_tokens, output_tokens,
  cells[id].latest_cost}` — from `admin/server.py:api_matrix` ✓
- `flag_id`, `session_id`, `title`, `model`, `status`, `why`, `last_activity_at`,
  `review.state` — from `_load_supervisor_flags` + `docs/supervisor_design.md §4` ✓
- `replay_complete` boundary — from `api_events` ✓
- `owned`/`external` ownership — from the claude-agent roster ✓

**DOM reconciliation.** All 17 current surfaces in `design.md §1.3`'s migration map exist in
`index.html` with matching ids/classes (`#pipeline-stages`, `.fleet-controls`, `#fleet-grid`,
`#fleet-counts`, `#claude-agents`, `#transcript-panel`, `#supervisor-rail`,
`#design-launchers`, `#design-start-form`, `#recent-designs`, the four `*-control-panel`s +
`#cell-control-panel`, `.bottom-rail`, `#routing-drawer`, `#registry-drawer`). The JS helpers
the design promises to reuse (`renderFleet`, `renderRail`, `renderBurn`, `stageCard`,
`normalizeStatus`, `sortCellIds`, `replaceEventSource`, `reconcileTelemetry`, `burnRate`) all
exist in `admin/static/app.js` / `control-room-core.js` ✓.

## 5. Findings & corrections

**F1 — Route-count prose error in `research.md §0.1` (corrected).** The research doc claimed
"only ~13 are POST." The accurate split is **15 POST (actuation) / 13 GET (read)**. The
conceptual point (reads dominate the surface and frequency; actuation is gated) is unaffected,
but the number was wrong. Fixed in `research.md` during verify. `design.md` does not repeat
the erroneous figure (its §1.2 table enumerates routes correctly), so no design change is
required.

**F2 — `Risk` filter facet is under-specified.** `design.md §2.1` retains the `Risk` chip but
does not state which statuses it matches. `research.md §2.11` explicitly flagged this as the
design's responsibility. **Minor gap**, not a grounding failure. Recommended fix for the
implementer: `Risk = {failed, timeout, retry}` (the three non-success, non-quiet states).

**F3 — One additional uncited numeric (48–56px rail).** Recorded in Check A item 4.

**F4 — Self-disclosed UNCITED items are consistent.** `design.md §10` claims "exactly three"
UNCITED choices; the audit agrees (the fourth in Check A is *not* self-disclosed, hence F3).

## 6. Verdict summary

| Check | Requirement | Result |
|---|---|---|
| A | Every design decision traces to a research source; uncited choices flagged | **PASS** (4 minor numerics) |
| B | Mobile specified explicitly (one-handed) | **PASS** |
| C | Flag-only rail visibly preserved | **PASS** |
| D | Maps to actual 28 routes + data shapes, no invented endpoints | **PASS** (with F1/F2) |

**Overall: PASS.** The design is grounded, mobile-first, flag-rail-preserving, and
implementable against the real 28 routes and the real `admin/static` DOM. The implementer
should resolve F2 (define `Risk`) and the four uncited numerics (Check A) before or during
implementation; none of these blocks the design.
