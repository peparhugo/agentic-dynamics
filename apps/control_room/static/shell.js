"use strict";

/**
 * Control Room — application shell (chrome only).
 *
 * This module owns everything that is *not* data: which board is visible, which theme is
 * applied, how dense the fleet grid is, where the single pipeline-stage strip is mounted, and
 * the System overflow sheet. It deliberately holds no experiment state, issues no fetch, and
 * opens no EventSource — the data layer (app.js) keeps that responsibility, and the Detail
 * surface's selection handoff lives in detail-sheet.js.
 *
 * Why a separate file rather than more of app.js: the chrome is the part a redesign changes
 * most often, and it must stay independently reviewable against docs/control_room_ui/design.md.
 * Everything here maps to a numbered design section, cited inline.
 *
 * Public surface (window.ControlRoomShell):
 *   showBoard(name)   — activate one of the five destinations           [design §1.2]
 *   openSystem()      — open the System overflow sheet                  [design §7.2]
 *   closeSystem()     — close it (Escape, scrim, close button)
 *   setTheme(name)    — "dark" | "light", persisted                     [design §8.1]
 *   setDensity(name)  — "comfortable" | "compact", persisted            [design §2.3]
 *   BOARDS            — the destination names, in nav order
 */
(function initControlRoomShell(root, core) {
  /** The five destinations, in nav order. System is an overflow, not a destination (§1.2). */
  const BOARDS = ["fleet", "status", "flags", "sessions", "routing"]

  /** localStorage keys. Namespaced so a shared origin cannot collide with other tools. */
  const THEME_KEY = "control-room-theme"
  const DENSITY_KEY = "control-room-density"
  const BOARD_KEY = "control-room-board"

  /** Query one shell element. Mirrors app.js's helper so both files read the same way. */
  function $(selector) {
    return document.querySelector(selector)
  }

  /** Query all matching shell elements as a real array. */
  function $$(selector) {
    return Array.from(document.querySelectorAll(selector))
  }

  /** Read a persisted preference without letting a disabled-storage browser break the shell. */
  function readStored(key) {
    try {
      return root.localStorage.getItem(key)
    } catch (_error) {
      return null
    }
  }

  /** Persist a preference, tolerating private-mode storage refusals. */
  function writeStored(key, value) {
    try {
      root.localStorage.setItem(key, value)
    } catch (_error) {
      /* Preference persistence is a convenience, never a correctness requirement. */
    }
  }

  /* ── Theme ────────────────────────────────────────────────────────────────────────────────
     One token set, two values (design §8.1): the theme only swaps the custom properties on
     <html data-theme>. index.html resolves the initial value pre-paint; this only handles the
     operator toggling it afterwards. */

  /** Apply and persist a theme, keeping the toggle's pressed state truthful. */
  function setTheme(name) {
    const theme = name === "light" ? "light" : "dark"
    document.documentElement.dataset.theme = theme
    writeStored(THEME_KEY, theme)
    const toggle = $("#theme-toggle")
    if (toggle) {
      toggle.setAttribute("aria-pressed", String(theme === "light"))
      toggle.title = theme === "light" ? "Toggle dark theme" : "Toggle light theme"
    }
  }

  /* ── Density ──────────────────────────────────────────────────────────────────────────────
     Layout-only (design §2.3): the same card DOM restyles, so this never touches rendering. */

  /** Apply and persist the fleet density, as a single class on the grid. */
  function setDensity(name) {
    const density = name === "compact" ? "compact" : "comfortable"
    const grid = $("#fleet-grid")
    if (grid) grid.classList.toggle("density-compact", density === "compact")
    writeStored(DENSITY_KEY, density)
    const toggle = $("#density-toggle")
    if (toggle) {
      toggle.setAttribute("aria-pressed", String(density === "compact"))
      toggle.title = density === "compact" ? "Switch to comfortable density" : "Toggle compact density"
    }
  }

  /* ── Region adoption ──────────────────────────────────────────────────────────────────────
     The design asks for the pipeline-stage strip on two boards: compact on Fleet (§2.1) and
     expanded on Status (§5.2). Cloning it would duplicate `id="pipeline-stages"` and break the
     data layer's single-element contract, so the shell re-parents the one real node into
     whichever board is active. app.js re-renders it by id on every poll, so it does not care
     where the node currently lives. */

  /** Move each single-instance region into the active board's matching mount point. */
  function adoptRegions(board) {
    const strip = $("#pipeline-stages")
    if (!strip) return
    // Fleet and Status both declare a `data-mount="stages"` slot; every other board omits it,
    // which parks the strip on Fleet (its home) while those boards are active.
    const target = $(`#board-${board} [data-mount="stages"]`) || $('#board-fleet [data-mount="stages"]')
    if (target && strip.parentElement !== target) target.appendChild(strip)
  }

  /* ── Board switching ──────────────────────────────────────────────────────────────────────
     Inactive boards keep the `hidden` attribute, so they leave both the tab order and the
     accessibility tree — the progressive-disclosure principle applies to keyboards too
     (design §1.1 principle 2). */

  /** Lazily press a board's own load control the first time the operator arrives (§7.1).
   *  Routing loads on demand in app.js behind `#routing-toggle`; rather than duplicating that
   *  logic, the shell presses the existing control once so the board is never blank. */
  function autoLoadBoard(board) {
    if (board !== "routing") return
    const drawer = $("#routing-drawer")
    const toggle = $("#routing-toggle")
    if (drawer && toggle && drawer.hidden) toggle.click()
  }

  /** Activate one destination; unknown names fall back to the home board. */
  function showBoard(name) {
    const board = BOARDS.includes(name) ? name : "fleet"
    document.body.dataset.board = board

    for (const section of $$(".board")) {
      section.hidden = section.dataset.board !== board
    }
    for (const destination of $$(".destination[data-board]")) {
      const active = destination.dataset.board === board
      if (active) destination.setAttribute("aria-current", "page")
      else destination.removeAttribute("aria-current")
    }

    adoptRegions(board)
    autoLoadBoard(board)
    writeStored(BOARD_KEY, board)

    // A board switch is a navigation, so the new board starts at its own top rather than
    // inheriting the previous board's scroll offset.
    const region = $("#boards")
    if (region) region.scrollTop = 0
  }

  /* ── Drawer toggle labels ─────────────────────────────────────────────────────────────────
     Routing and Registry each keep an explicit show/hide control, and the data layer owns what
     pressing it does (lazy fetch, focus handling, Escape). The shell owns only its LABEL: a
     button that says "Show routing data" while the data is already showing is a small lie the
     operator has to test by pressing it. Driven off `aria-expanded`, which app.js already
     maintains, so there is no second source of truth for the open state. */

  /** Keep one drawer toggle's label in sync with the state it reports. */
  function syncToggleLabel(toggle, noun) {
    if (!toggle) return
    const expanded = toggle.getAttribute("aria-expanded") === "true"
    const label = `${expanded ? "Hide" : "Show"} ${noun}`
    if (toggle.textContent.trim() !== label) toggle.textContent = label
  }

  /** Observe both drawer toggles and relabel them whenever their state changes. */
  function bindToggleLabels() {
    const toggles = [
      [$("#routing-toggle"), "routing data"],
      [$("#registry-toggle"), "registry"],
    ]
    for (const [toggle, noun] of toggles) {
      if (!toggle) continue
      syncToggleLabel(toggle, noun)
      if (typeof MutationObserver !== "function") continue
      new MutationObserver(() => syncToggleLabel(toggle, noun)).observe(toggle, {
        attributes: true,
        attributeFilter: ["aria-expanded"],
      })
    }
  }

  /* ── System overflow sheet ────────────────────────────────────────────────────────────────
     Registry + Queue actions: occasional surfaces that are not glance-worthy enough for a tab
     (design §1.2, §7.2). Bottom sheet on mobile, centered panel on desktop — one DOM, styled
     per breakpoint. */

  let systemReturnFocus = null
  const SYSTEM_FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

  /** Respect the operating system motion preference for utility-form handoffs. */
  function scrollBehavior() {
    return root.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
  }

  /**
   * Keep keyboard focus inside System while its scrim makes the board unavailable.
   *
   * Detail already has this behavior on small screens. System needs the same modal contract on
   * every viewport because its dialog and scrim are visible together on both phone and desktop.
   */
  function trapSystemFocus(event) {
    if (event.key !== "Tab") return
    const sheet = $("#system-sheet")
    if (!sheet || sheet.dataset.open !== "true") return
    const focusable = Array.from(sheet.querySelectorAll(SYSTEM_FOCUSABLE)).filter(
      (node) => !node.closest("[hidden]"),
    )
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  /** Reflect the sheet's open state on both affordances that can open it. */
  function markSystemToggles(open) {
    for (const toggle of [$("#system-toggle"), $("#system-nav")]) {
      toggle?.setAttribute("aria-expanded", String(open))
    }
  }

  /** Open the System sheet, load the registry once, and park focus inside it. */
  function openSystem() {
    const sheet = $("#system-sheet")
    if (!sheet || sheet.dataset.open === "true") return
    systemReturnFocus = document.activeElement
    sheet.hidden = false
    sheet.dataset.open = "true"
    markSystemToggles(true)
    showScrim()

    // Same lazy-load bridge as the Routing board: press the existing control rather than
    // re-implementing app.js's fetch + focus handling.
    const drawer = $("#registry-drawer")
    const toggle = $("#registry-toggle")
    if (drawer && toggle && drawer.hidden) toggle.click()
    else $("#system-close")?.focus()
  }

  /** Close the System sheet and return focus to whatever opened it. */
  function closeSystem() {
    const sheet = $("#system-sheet")
    if (!sheet || sheet.dataset.open !== "true") return
    sheet.dataset.open = "false"
    sheet.hidden = true
    markSystemToggles(false)
    hideScrimIfIdle()
    if (systemReturnFocus instanceof HTMLElement) systemReturnFocus.focus()
    systemReturnFocus = null
  }

  /* ── Scrim ────────────────────────────────────────────────────────────────────────────────
     Shared by the System sheet and the Detail sheet, because at most one modal surface is
     open at a time on mobile. Detail sheet code calls these through the exported helpers. */

  /** Show the modal scrim and lock the board behind it from scrolling. */
  function showScrim() {
    const scrim = $("#scrim")
    if (scrim) scrim.hidden = false
    document.body.classList.add("sheet-open")
  }

  /** Hide the scrim only when no modal surface still needs it. */
  function hideScrimIfIdle() {
    const systemOpen = $("#system-sheet")?.dataset.open === "true"
    const detailModal = document.body.classList.contains("detail-modal")
    if (systemOpen || detailModal) return
    const scrim = $("#scrim")
    if (scrim) scrim.hidden = true
    document.body.classList.remove("sheet-open")
  }

  /* ── Wiring ─────────────────────────────────────────────────────────────────────────────── */

  /** Bind every chrome control exactly once. */
  function bindShell() {
    for (const destination of $$(".destination[data-board]")) {
      destination.addEventListener("click", () => showBoard(destination.dataset.board))
    }

    $("#system-toggle")?.addEventListener("click", () => {
      if ($("#system-sheet")?.dataset.open === "true") closeSystem()
      else openSystem()
    })
    $("#system-nav")?.addEventListener("click", () => {
      if ($("#system-sheet")?.dataset.open === "true") closeSystem()
      else openSystem()
    })
    $("#system-close")?.addEventListener("click", closeSystem)

    $("#theme-toggle")?.addEventListener("click", () => {
      setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light")
    })

    $("#density-toggle")?.addEventListener("click", () => {
      const grid = $("#fleet-grid")
      setDensity(grid?.classList.contains("density-compact") ? "comfortable" : "compact")
    })

    // The scrim dismisses the topmost modal surface: System first, then Detail.
    $("#scrim")?.addEventListener("click", () => {
      if ($("#system-sheet")?.dataset.open === "true") closeSystem()
      else root.ControlRoomDetail?.close()
    })

    // Escape closes the System sheet here; the Detail sheet handles its own Escape so the
    // two surfaces never fight over one key.
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && $("#system-sheet")?.dataset.open === "true") {
        closeSystem()
        return
      }
      trapSystemFocus(event)
    })
  }

  /* ── Rail mirrors ─────────────────────────────────────────────────────────────────────────
     The canonical telemetry outputs live on the Status board (design §5.2); the slim command
     rail shows the same numbers so the operator keeps orientation from any board (§1.3).
     Element ids must stay unique, so the rail carries `data-mirror` spans that this observer
     keeps in sync — no second writer, no fork of the data layer. */

  /** Mirror one canonical node's text into every span that declares it as its source. */
  function syncMirror(sourceId) {
    const source = document.getElementById(sourceId)
    if (!source) return
    const text = source.textContent.trim()
    for (const mirror of $$(`[data-mirror="${sourceId}"]`)) {
      mirror.textContent = text
      // The Flags badge is the one mirror that hides itself when there is nothing to say:
      // a zero count must not read as an alert (design §4.2).
      if (mirror.classList.contains("destination-badge")) {
        mirror.hidden = !text || text === "0" || text === "--"
      }
    }
  }

  /** Observe the canonical outputs and mirror them as the data layer rewrites them. */
  function bindMirrors() {
    const sources = Array.from(new Set($$("[data-mirror]").map((node) => node.dataset.mirror)))
    if (!sources.length || typeof MutationObserver !== "function") return
    const observer = new MutationObserver((records) => {
      const touched = new Set()
      for (const record of records) {
        const node = record.target instanceof Element ? record.target : record.target.parentElement
        const owner = node?.closest("[id]")
        if (owner && sources.includes(owner.id)) touched.add(owner.id)
      }
      for (const id of touched) syncMirror(id)
    })
    for (const id of sources) {
      const source = document.getElementById(id)
      if (!source) continue
      observer.observe(source, { childList: true, characterData: true, subtree: true })
      syncMirror(id)
    }
  }

  /* ── On-demand forms ─────────────────────────────────────────────────────────────────────
     The two "start a session" forms sit below their board's resting content and are revealed
     by the data layer flipping `hidden` (app.js owns that, because it also fills the approved
     workdir options). The shell only reacts to the reveal: it scrolls the form into view so
     the launcher the operator pressed and the form it opened stay visually connected, and it
     focuses the form's first field, which on a phone is what raises the keyboard. */

  /** Bring a just-revealed on-demand form into view and focus its first control. */
  function revealForm(form) {
    if (form.hidden) return
    // Guarded: scrollIntoView is absent in some non-browser DOM implementations, and a missing
    // convenience must never take down the shell's boot path.
    if (typeof form.scrollIntoView === "function") form.scrollIntoView({ block: "nearest", behavior: scrollBehavior() })
    const field = form.querySelector("textarea, input, select")
    if (field instanceof HTMLElement) field.focus({ preventScroll: true })
  }

  /** Watch the on-demand forms for the data layer un-hiding them. */
  function bindOnDemandForms() {
    if (typeof MutationObserver !== "function") return
    for (const selector of ["#design-start-form", "#claude-agent-start-form"]) {
      const form = $(selector)
      if (!form) continue
      new MutationObserver(() => revealForm(form)).observe(form, {
        attributes: true,
        attributeFilter: ["hidden"],
      })
    }
  }

  /* ── Boot ─────────────────────────────────────────────────────────────────────────────────
     Runs before app.js so the chrome is interactive during the first poll. Restores the
     operator's last board, theme, and density — orientation survives a reload. */

  function boot() {
    bindShell()
    bindMirrors()
    bindOnDemandForms()
    bindToggleLabels()
    setTheme(document.documentElement.dataset.theme)
    setDensity(readStored(DENSITY_KEY) || "comfortable")
    showBoard(readStored(BOARD_KEY) || "fleet")
  }

  const shell = {
    BOARDS,
    showBoard,
    openSystem,
    closeSystem,
    setTheme,
    setDensity,
    showScrim,
    hideScrimIfIdle,
    // Re-exported so the Detail sheet and any future board module use one status vocabulary
    // instead of re-deriving it (core.normalizeStatus is the single source of truth).
    normalizeStatus: core ? core.normalizeStatus : (value) => String(value || "unknown"),
  }

  root.ControlRoomShell = shell
  if (typeof module !== "undefined" && module.exports) module.exports = shell
  boot()
})(typeof globalThis !== "undefined" ? globalThis : window, (typeof globalThis !== "undefined" ? globalThis : window).ControlRoomCore)
