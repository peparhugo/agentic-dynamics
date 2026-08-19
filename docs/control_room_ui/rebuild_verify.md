# Control Room UI Rebuild — Implementation Verification

> **Scope.** This document traces the **rebuilt implementation** in `admin/static/` back to
> `docs/control_room_ui/design.md` §1–§8, section by section, with a PASS/FAIL verdict and the
> file:line where each decision actually lives.
>
> It is **not** the same document as `docs/control_room_ui/verify.md`, which verifies the
> *design phase* (that every design decision carries an `[R §x.y]` research citation, that the
> `UNCITED` choices are enumerated, and that the design invents no endpoint). This one asks a
> different question: **did the rebuild ship what the design specified, and did it break
> anything?**
>
> Method: three independent evidence sources, all reproducible.
>
> 1. **The repository test suite** — `pytest tests/ -m "not external" -q`.
> 2. **Static invariant checks** — route enumeration against the running Flask app, and
>    source-level greps over `admin/static/`.
> 3. **Runtime behavior harnesses** — the static app booted in jsdom behind controllable fake
>    APIs, driving real poll cycles, clicks, and pointer gestures. These verify the properties
>    that are invisible to a source-level test (does a no-op poll actually mutate the DOM? does
>    the sheet actually dismiss on a flick?). jsdom is **not** a repository dependency — the
>    codebase deliberately has no JavaScript runtime dependency — so these harnesses live
>    outside the repo and are reproduced from the recipe in the appendix.
>
> Line references are as of the commit that adds this document.

---

## 0. Gate results

| Gate | Command | Result |
|---|---|---|
| Full regression | `pytest tests/ -m "not external" -q` | **1087 passed**, 101 deselected, 0 failed |
| Admin/front-end subset | `pytest tests/test_admin_frontend.py tests/test_admin_server.py -q` | **51 passed** |
| Shell runtime harness | `node smoke.js` (jsdom) | **29/29 checks** |
| Fleet runtime harness | `node fleet.js` (jsdom) | **37/37 checks** |
| Boards + Detail harness | `node boards.js` (jsdom) | **69/69 checks** |
| Computed-style harness | `node css.js` (jsdom) | **18/18 checks** |

**Verdict: PASS.** No test was modified, skipped, or relaxed at any point in the rebuild; every
structural assertion the pre-existing suite made about `index.html`, `style.css`, and `app.js`
still holds against files that were rewritten from scratch.

---

## 1. Invariants

These are the four properties that must survive a from-scratch rebuild, because breaking any of
them changes what the Control Room *is*, not merely how it looks.

### 1.1 No new endpoint — the 28-route surface is unchanged — **PASS**

The rebuild touched **zero backend files**: `git diff --stat HEAD -- admin/server.py src/ scripts/`
is empty. Enumerating the live route map confirms the count the design asserts:

```
non-static rule objects: 28   (26 distinct paths: 25 under /api, plus "/")
```

The 28-vs-26 difference is not a discrepancy: `/api/design-sessions` and `/api/claude-agents`
each register two rule objects (GET and POST), which is how the design's own "28 routes"
figure counts them.

Every endpoint the client calls, extracted from `admin/static/app.js` by parsing its `fetch(...)`
and `EventSource(...)` call sites:

| Method | Endpoint | Consumed by |
|---|---|---|
| GET | `/api/matrix` | Fleet + Status (5s poll) |
| GET | `/api/flags?limit=50` | Flags (5s poll) |
| GET | `/api/design-sessions`, `/api/design-sessions/<id>/spec` | Sessions, Detail |
| GET | `/api/claude-agents`, `…/daemon`, `…/<id>/logs` | Sessions, Detail |
| GET | `/api/routing` | Routing |
| GET | `/api/registry`, `/api/registry/<id>` | System |
| POST | `/api/experiments` | System (queue actions) |
| POST | `/api/flags/<id>/steer`, `…/interrupt` | Detail (supervisor mode, gated) |
| POST | `/api/design-sessions/<id>/{input,save,run,interrupt}` | Detail (design mode) |
| POST | `/api/claude-agents/<id>/{stop,respawn,rm,steer}` | Detail (agent mode, owned only) |
| SSE | `/api/status` | global connection state |
| SSE | `/api/events/<cell_id>` | the one selected-detail stream |

No endpoint outside this list is referenced, and none was added.

### 1.2 Flag-only rail — **PASS**

`docs/supervisor_design.md`'s invariant is that the supervisor **observes and never steers**;
the rail surfaces flags, and only a human acts on them. Three structural facts hold:

- The Flags **board render path contains no actuation at all.** Slicing `app.js` between the
  `── Flags board ──` and `── Sessions board ──` section banners and searching for `fetch(`,
  `Mutation(`, and `method: "POST"` returns nothing for all three. Selecting a row calls
  `selectSupervisorFlag()`, which opens the Detail surface and sends no request
  (`app.js:698` render path; delegated listener bound in `bindControls`).
- The only two flag actuations, `supervisorMutation('/api/flags/<id>/steer')` (`app.js:2080`) and
  `…/interrupt` (`app.js:2134`), live in the **Detail** surface's supervisor panel, behind the
  deliberate Steer composer and the typed Interrupt door.
- The boundary copy **"Supervisor flags. You decide."** appears twice, exactly as
  `docs/supervisor_design.md §1` requires: on the board (`index.html:473`, verified by the
  boards harness) and above the actions in the Detail panel (`index.html:225`, verified by the
  same harness).

### 1.3 Single-context handoff — **PASS**

At most one selected-detail `EventSource` and one status `EventSource` may exist (design §1.1
principle 3).

- Only `app.js` ever constructs an `EventSource`. `shell.js`, `detail-sheet.js`,
  `board-fleet.js`, and `keyed-list.js` contain zero constructions (the single textual match in
  `shell.js:9` is a docstring stating that it opens none).
- The selected stream is replaced through `core.replaceEventSource`, which closes before it
  constructs — an ordering the pre-existing test asserts by comparing source offsets
  (`tests/test_admin_frontend.py:39-41`), and which still passes.
- Every selection entry point (`selectCell`, `selectDesignSession`, `selectSupervisorFlag`,
  `selectClaudeAgent`) closes `state.eventSource` before switching context.
- The status stream is idempotent: `if (state.statusSource) return` (`app.js:1764`).
- Exactly one transcript feed exists in the document — asserted by the pre-existing test
  (`html.count('id="transcript-feed"') == 1`) and re-checked at runtime by the boards harness.

### 1.4 `textContent`-only rendering — **PASS**

Cell ids, session ids, flag rationales, and log tails are untrusted producer data. A grep over
every file in `admin/static/*.js` for `innerHTML`, `outerHTML`, `insertAdjacentHTML`,
`document.write`, and `eval(` returns **no matches**. All rendering goes through
`element(tag, className, text)` (which assigns `textContent`) or the reconciler's
`setText`/`setAttribute` helpers (`keyed-list.js:33`).

### 1.5 Mobile-first actually works — **PASS**

Not merely "there is a media query" — the base cascade *is* the phone, and desktop is additive:

| Check | Evidence |
|---|---|
| Bottom tab bar is the base nav | `.destinations { position: fixed; bottom: 0 }` in the pre-query cascade (`style.css:361`) |
| Detail is a bottom sheet in the base | base `border-radius: … 0 0` + `max-height: 92dvh` |
| Fleet grid is single-column in the base | `grid-template-columns: minmax(0, 1fr)` |
| Safe-area insets in the base | `env(safe-area-inset-bottom)` on the tab bar, sheets, and boards |
| 44px touch targets in the base | `--touch-target: 44px` (`style.css` §1 tokens) |
| The left rail exists **only** under `min-width` | `.destinations` restyled inside `@media (min-width: 760px)` (`style.css:1666`) |

Media-query inventory, in source order: `(max-width: 759px)` mobile-only, `(min-width: 760px)`
desktop, `(min-width: 1200px)` wide, `(max-width: 420px)` hard compaction,
`(prefers-reduced-motion: reduce)`. Two additive desktop blocks against two mobile-only blocks —
the shape of a mobile-first sheet, not a desktop sheet with phone patches.

Behaviorally: the boards harness pins jsdom to a phone viewport (`matchMedia` reports the
`max-width: 759px` query as matching) and all 69 checks pass there, including the modal sheet,
its focus trap, and the drag gesture.

---

## 2. Section-by-section trace

### §1 Information architecture — **PASS**

| Design requirement | Where it lives | Verdict |
|---|---|---|
| §1.2 five destinations + System overflow | `index.html:98` (`#destinations`, five `data-board` buttons + `#system-nav`) | PASS |
| §1.2 board → route mapping | see §1.1 table above; no invented endpoint | PASS |
| §1.3 migration of every old DOM surface | Fleet `index.html:359`, Status `:405`, Flags `:453`, Sessions `:478`, Routing `:589`, System `:622` | PASS |
| §1.4 desktop left rail / mobile bottom tab bar, **one DOM** | one `<nav>` restyled at `style.css:361` (base) and `:1666` (desktop) | PASS |
| §1.4 System reached from a rail entry (desktop) and a shell gear (mobile) | `#system-nav` + `#system-toggle`, one handler (`shell.js:197`) | PASS |
| §1.5 Detail is transversal, never a tab | `index.html:138`; opened only by drill-down delegation (`detail-sheet.js:104`) | PASS |
| §1.1.6 calm under load | keyed reconciliation for all four polled lists (`keyed-list.js:88`) | PASS |

**Implementation note (documented deviation, not a gap).** §5.2 wants the pipeline-stage strip
on both Fleet and Status. Cloning it would duplicate `id="pipeline-stages"` and break the data
layer's single-element contract, so `shell.js:102` (`adoptRegions`) **re-parents the one real
node** into whichever board declares a `data-mount="stages"` slot. Verified at runtime: the
strip follows the active board and parks on Fleet for boards without a slot.

Likewise, the slim command rail shows **mirrors** of the canonical Status-board outputs
(`shell.js:295`, `syncMirror` via `MutationObserver`) rather than second copies, because ids
must stay unique. There is one writer (the data layer) and one source of truth.

### §2 Fleet overview — **PASS**

| Requirement | Where | Verdict |
|---|---|---|
| §2.1 urgency-first matrix, stage strip above it | `board-fleet.js:117` (`visibleCellIds`, ordering delegated to `core.sortCellIds`) | PASS |
| §2.2 two axes, never sharing a hue family or class prefix | `board-fleet.js:44` (`LIFECYCLE`, `status-*`) and `:62` (`ATTENTION`, `flag-status-*`) | PASS |
| §2.2 glyph + word + color, color never alone | `applyStatusWord` (`app.js:181`) emits an `aria-hidden` glyph span + the word; CSS supplies color only | PASS |
| §2.2 attention hues never on a fleet card | asserted at runtime (`no attention vocabulary on a fleet card`) | PASS |
| §2.3 density toggle, persisted | `shell.js:82` (`setDensity` + `localStorage`); 132/84px cards, 190/150px columns at desktop | PASS |
| §2.4 one-tap drill-down, no interstitial | whole card is one `<button>`; delegated click → `selectCell` → Detail opens | PASS |
| §2.5 counts footer, re-rendered in place | `board-fleet.js:130` (`countsSummary`), written through `setText` | PASS |
| §2.5 stable row identity, no reflow on a no-op poll | `cellSignature` (`board-fleet.js:149`) + `reconcile`; **zero DOM mutations measured** across an identical poll | PASS |

The zero-mutation result is measured, not asserted: the harness attaches a `MutationObserver` to
`#fleet-grid` (childList + subtree + attributes + characterData), lets a full 5s poll cycle
elapse with an unchanged payload, and requires the record count to be exactly 0. Focus placed on
a card before the poll is still there after it.

### §3 Detail surface — **PASS**

| Requirement | Where | Verdict |
|---|---|---|
| §3.1 modal bottom sheet on mobile, docked column on desktop | `style.css` base (sheet) + `@media (min-width: 760px)` (column, via `:has()`) | PASS |
| §3.1 drag handle + swipe-to-dismiss | `detail-sheet.js:181-215` (Pointer Events, capture, distance **or** flick velocity) | PASS |
| §3.1 back affordance | `#detail-close` reads "Back" on mobile, a close glyph on desktop (one button, one handler) | PASS |
| §3.1 safe-area aware | `padding-bottom: env(safe-area-inset-bottom)` on the sheet | PASS |
| §3.2 glanceable-first field order | header = identity → status → phase → cost/tokens (`index.html:159`, `renderDetailGlance` at `app.js:862`) | PASS |
| §3.2 long prose last, clamped, expandable | `.prose-clamp` (`style.css:1156`) + `toggleProse` (`detail-sheet.js:236`), keyboard-operable | PASS |
| §3.3 one transcript, follow/pause/clear, `jump-live` off-tail | unchanged contract, restyled | PASS |
| §3.3 follow control in the thumb zone on mobile | flex `order` reordering inside `@media (max-width: 759px)` | PASS |
| §3.4 `READ ONLY` / `INTERACTIVE` mode line | `#ownership-badge`; verified INTERACTIVE for an owned session at runtime | PASS |
| §3.4 reversible = primary, irreversible = danger + typed door | Interrupt door (pre-existing) and the new queue door (`app.js:2628`) | PASS |
| §3.4 supervisor boundary above the actions | verified at runtime | PASS |

The gesture is verified by dispatching **real** pointer events: a 20px drag springs back (sheet
stays open, transform cleared), a 200px drag dismisses, and a 40px/40ms flick dismisses on
velocity. The handle is also a real `<button>`, so keyboard and screen-reader users get the same
dismissal without the gesture.

### §4 Flags board — **PASS**

| Requirement | Where | Verdict |
|---|---|---|
| §4.1 full board, not a buried rail | `index.html:453`; `.board-flags { min-height: 100% }` with the list scrolling inside | PASS |
| §4.2 count badge + source/degraded line | `#supervisor-count`, `#supervisor-source` (`index.html:462`), `#supervisor-delay` | PASS |
| §4.2 rows: status word + title + clamped `why` + model + ages | `createSupervisorRow` (`app.js:617`) | PASS |
| §4.2 rows update **in place**, no reorder, no focus theft | keyed reconciliation; **zero DOM mutations measured** on a no-op poll, focus survives | PASS |
| §4.2 announcements only on new session or changed assessment | `loadSupervisorFlags` (unchanged logic) | PASS |
| §4.2 three states rendered verbatim | empty / flagged / degraded all exercised at runtime, including "degraded keeps the retained rows" | PASS |
| §4.2 a nonzero count never yanks the operator to the board | badge mirrors the count; no auto-navigation exists | PASS |
| §4.3 board is pure read | no `fetch`/mutation in the board render path (§1.2 above) | PASS |

**Documented deviation.** §4.2 says rows update "in place by `flag_id`". `flag_id` is a
server-side **digest of the flag's fields** (`src/instrument/supervisor.py:46`), so it changes
whenever the assessment changes. Keying rows by it would destroy and rebuild a row on exactly
the event the requirement exists to survive. The implementation therefore keys rows by
**`session_id`** (the stable identity of the thing being flagged) and uses **`flag_id` as the
row's revision** inside the change signature (`app.js:617` section comment). This delivers the
requirement's intent — a poll never reorders or steals focus, and an assessment change repaints
the same node — which is verified at runtime ("assessment change repaints the row in place").

### §5 Status board — **PASS**

| Requirement | Where | Verdict |
|---|---|---|
| §5.2 reported spend (large) | `#reported-spend`, `.metric-hero` at 24px | PASS |
| §5.2 burn with the **full** trace (the rail keeps only a number) | `#burn-trace` at `0 0 240 48` over 60 samples (`app.js:229`); the rail carries a `data-mirror` number | PASS |
| §5.2 input/output totals + `history_capped` provenance | `#input-tokens`, `#output-tokens`, `#spend-provenance` (`RETAINED WINDOW · TRUNCATED`) | PASS |
| §5.2 three pipeline stages expanded | adopted strip, one-column expanded variant on this board | PASS |
| §5.2 Redis/connection state + provenance label | `#redis-state`, `.bottom-provenance` | PASS |
| §5.2 no new endpoint | `/api/matrix` + `/api/status` only | PASS |

### §6 Sessions board — **PASS**

| Requirement | Where | Verdict |
|---|---|---|
| §6.2 design launchers + start form + recent list | `index.html:478` onward | PASS |
| §6.2 Claude daemon panel + start form + roster | same board; daemon stop is danger-styled and confirmed | PASS |
| §6.2 ownership chip per roster card | `updateClaudeAgentCard` (`app.js`), chips verified OWNED/EXTERNAL at runtime | PASS |
| §6.2 ownership controls mirror (never add to) the backend gate | `#claude-agent-owned-controls` / `#claude-agent-external-controls` toggled from `entry.owned`; server still enforces `_require_owned_claude_agent` | PASS |
| §6.2 selecting a session opens Detail in the right mode | verified at runtime (claude panel shown, other three hidden) | PASS |
| §1.1.6 calm under load | both rosters keyed; **zero DOM mutations measured** on a no-op 10s poll | PASS |

**Implementation note.** The design-session start form sits below the recent list rather than
immediately under the launchers, and `shell.js` scrolls it into view and focuses its first field
when the data layer reveals it. The ordering is required by a pre-existing structural test that
slices the document positionally; the scroll-and-focus keeps the pressed launcher and the form
it opened connected despite the distance.

### §7 Routing board + System overflow — **PASS**

| Requirement | Where | Verdict |
|---|---|---|
| §7.1 Routing promoted to a full read-only board | `index.html:589`; runtime check: no forms, no danger actions, GET-only requests | PASS |
| §7.1 Refresh action | `#routing-refresh` | PASS |
| §7.1 dense table uses the card→list→table compaction | `.table-scroll` + sticky headers | PASS |
| §7.2 System reached via a sheet (mobile) / centered panel (desktop) | `index.html:622` | PASS |
| §7.2 Registry = filterable table + one-hop lineage, read-only | `#registry-filters`, `#registry-lineage`; GET-only | PASS |
| §7.2 Queue: `Enqueue` primary, `Clear queued work` danger **and gated** | typed door (`app.js:2628`) | PASS |

The queue door is verified end-to-end at runtime: it starts closed; opening it leaves the
confirm disarmed; a near-miss phrase (`clear queue`, wrong case) keeps it disarmed and a click
in that state sends **nothing**; the exact phrase `CLEAR QUEUE` arms it; confirming posts exactly
once to `/api/experiments`; the door then closes. This replaces a `window.confirm()` dialog,
per §3.4's rule that irreversible actions get a two-step typed door rather than a dialog that
can be dismissed by reflex.

Both drawer toggles relabel themselves from `aria-expanded` (`shell.js:158`), so a button never
reads "Show routing data" over data that is already showing.

### §8 Visual system — **PASS**

| Requirement | Where | Verdict |
|---|---|---|
| §8.1 dark default, full light theme, one token set | `style.css:35` (`:root`) and `:110` (`[data-theme="light"]`); pre-paint resolution inline in `index.html` avoids a flash | PASS |
| §8.2 the concrete palette | **all 23 tokens × 2 themes match the design's values byte-for-byte** (diffed programmatically against the design's CSS block) | PASS |
| §8.2 accent reserved for interactivity | `--accent` used for focus ring, active destination, primary CTA only | PASS |
| §8.3 4px spacing scale | `--sp-1: 4px` … `--sp-6: 32px` (`style.css:69`) | PASS |
| §8.4 Inter + mono stacks | `--font-ui`, `--font-mono` (`style.css:77`) | PASS |
| §8.4 tabular numerals on counters | `font-variant-numeric: tabular-nums` on `body` | PASS |
| §8.5 motion only on state transitions | only the running-cell border pulse animates (`style.css:1829`); cards update in place | PASS |
| §8.5 honor `prefers-reduced-motion` | `style.css:1836`; the sheet gesture also skips its follow-transform under it | PASS |

---

## 3. Defects found and fixed during the rebuild

Recorded because each one was a real bug that the runtime harnesses caught and no source-level
test could have.

| # | Defect | Fix |
|---|---|---|
| 1 | `setAttribute("aria-busy", …)` re-wrote an unchanged value every poll, queuing a mutation record — enough to re-announce a busy region every 5s | write-on-change (`keyed-list.js:33`) |
| 2 | The UA's `[hidden] { display: none }` is user-agent origin, so every author `display: flex` rule defeated it — `#design-control-panel`, `#supervisor-control-panel`, `#claude-agent-control-panel`, both drawers, and both start forms would never actually hide | one global rule, deliberately the last in the file so it wins on order *and* importance (`style.css:1857`) |
| 3 | Static first-paint placeholders shipped in `index.html` were left stranded above rendered rows forever, showing "Loading supervisor flags…" over a loaded board | renderers adopt the existing node (`adoptPlaceholder`, `app.js:334`) |
| 4 | An unguarded `scrollIntoView` could throw during boot in DOM implementations lacking it | guarded in `shell.js` and `detail-sheet.js` |

---

## 4. What is **not** claimed

Stated plainly so the next reader does not over-read this document.

- **No real-browser rendering was verified.** jsdom evaluates the cascade but does no layout: it
  cannot confirm that a card grid visually reflows at 760px, that the sheet's 92dvh height looks
  right on a notched phone, or that the glyphs render in the chosen fonts. Every layout claim
  here is a claim about the *rules*, not about pixels. A human pass on a real device remains
  the only way to confirm the visual result.
- **No touch-hardware gesture test.** The drag is verified with synthesized Pointer Events;
  momentum, palm rejection, and browser-native overscroll interactions are untested.
- **`app.js` is still one 2862-line file.** The rebuild extracted the chrome (`shell.js`),
  the Detail surface (`detail-sheet.js`), the status vocabulary and fleet logic
  (`board-fleet.js`), and list reconciliation (`keyed-list.js`) into reviewable modules, and
  rewrote every polled renderer inside `app.js`. Splitting the remaining data layer into
  per-board modules is a further step this rebuild did not take, partly because the existing
  test suite pins several source-level strings to `app.js`.
- **Accessibility was engineered, not audited.** Focus management, the modal focus trap, live
  regions, `aria-pressed`/`aria-current`, decorative-glyph marking, and 44px targets are all
  implemented and partly verified at runtime, but no screen-reader pass or automated a11y audit
  (axe, Lighthouse) was run.

---

## Appendix — reproducing the runtime harnesses

The harnesses are intentionally outside the repository, because `admin/static/` is a no-build,
no-dependency asset set and adding a JS test runner would change that contract.

```bash
npm install jsdom@22 --prefix /tmp/crsmoke     # jsdom 23+ is ESM-only and needs Node 22+
node /tmp/crsmoke/smoke.js      # 29 checks — shell: nav, theme, density, sheets, mirrors
node /tmp/crsmoke/fleet.js      # 37 checks — fleet: order, status, facets, zero-mutation poll
node /tmp/crsmoke/boards.js     # 69 checks — flags/status/sessions/routing/system + Detail
node /tmp/crsmoke/css.js        # 18 checks — computed styles for every hidden/visible region
```

Each harness reads `admin/static/index.html`, derives its script list from the page's own
`<script src>` tags (so it cannot drift from what the browser loads), stubs `fetch`,
`EventSource`, `PointerEvent`, and `matchMedia`, and then drives the **real, unmodified**
application code.
