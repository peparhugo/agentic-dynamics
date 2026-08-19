"use strict";

/**
 * Control Room — the transversal Detail surface.
 *
 * Detail is the third depth of the disclosure chain (fleet -> node -> stream, design §1.1
 * principle 2). It is never a destination: it only ever appears as the *result* of selecting
 * a node on a board (design §1.5). This module owns that surface's presentation — when it
 * opens, how it behaves as a modal bottom sheet on a phone, and how focus moves — and nothing
 * else. It does not fetch, does not stream, and does not decide which control panel to show:
 * app.js already does all three, keyed off `selectedType`.
 *
 * The one contract between the two files is the DOM: any click on a node-selection control
 * (`.cell-select`, `.supervisor-flag`, `.recent-design`) means "a node was selected", so the
 * sheet opens. Delegation keeps that contract one-way, which is why re-rendering the fleet on
 * every 5s poll — which replaces those buttons wholesale — cannot desynchronize the sheet.
 *
 * Public surface (window.ControlRoomDetail):
 *   open(trigger)  — reveal the surface, remembering where focus came from
 *   close()        — hide it and restore focus                          [design §3.3]
 *   isModal()      — true below the 760px breakpoint                    [design §1.4]
 */
(function initControlRoomDetail(root, core) {
  /** Below this width the surface is a modal bottom sheet; at or above it, a docked column. */
  const MODAL_QUERY = "(max-width: 759px)"

  /** Selectors that mean "the operator selected a node" (§1.5: cell, flag, design, agent). */
  const SELECTION_CONTROLS = ".cell-select, .supervisor-flag, .recent-design"

  /** Focusable descendants, for the mobile focus trap. */
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

  /** The control that opened the sheet, so Escape/close can hand focus back to it. */
  let returnFocus = null

  /** Query one element. */
  function $(selector) {
    return document.querySelector(selector)
  }

  /** The detail surface root, or null before the shell has parsed. */
  function surface() {
    return $("#detail-surface")
  }

  /** True when the viewport renders Detail as a modal sheet rather than a docked column. */
  function isModal() {
    return typeof root.matchMedia === "function" && root.matchMedia(MODAL_QUERY).matches
  }

  /**
   * Mirror the selected node's lifecycle status onto the surface.
   *
   * Read from the DOM rather than from app.js state on purpose: the status word is already
   * rendered inside the selection control, and `core.normalizeStatus` is the single source of
   * truth for collapsing producer variants (e.g. `retry_3` -> `retry`). Re-deriving it here
   * would be a second vocabulary (design §2.2).
   */
  function reflectStatus(trigger) {
    const node = surface()
    if (!node) return
    const card = trigger?.closest?.("[class*='status-']")
    const match = card ? /status-([a-z_]+)/.exec(card.className) : null
    const status = core ? core.normalizeStatus(match ? match[1] : "") : "unknown"
    node.dataset.status = status
  }

  /** Move focus into the sheet without stealing it from a text field the operator is using. */
  function focusSheet() {
    const node = surface()
    if (!node) return
    const active = document.activeElement
    if (node.contains(active)) return
    const target = $("#detail-close") || node.querySelector(FOCUSABLE)
    target?.focus({ preventScroll: true })
  }

  /**
   * Keep Tab inside the sheet while it is modal.
   *
   * A modal bottom sheet that leaks focus to the dimmed board behind it is worse than no
   * sheet at all on a phone: the operator tabs into controls they cannot see ([R §1.4.1],
   * [R §2.7]). The trap is intentionally only installed while modal — on desktop the surface
   * is a docked column and must stay in the normal tab order.
   */
  function trapTab(event) {
    if (event.key !== "Tab" || !isModal()) return
    const node = surface()
    if (!node || node.dataset.open !== "true") return
    const focusable = Array.from(node.querySelectorAll(FOCUSABLE)).filter((element) => element.offsetParent !== null)
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

  /** Reveal the Detail surface, remembering the control that opened it. */
  function open(trigger) {
    const node = surface()
    if (!node) return
    if (trigger instanceof HTMLElement) returnFocus = trigger
    reflectStatus(trigger)
    const wasOpen = node.dataset.open === "true"
    node.dataset.open = "true"
    if (isModal()) {
      // The scrim and the body scroll lock are shared with the System sheet, so they are
      // owned by the shell — this module only declares that Detail currently needs them.
      document.body.classList.add("detail-modal")
      root.ControlRoomShell?.showScrim()
      if (!wasOpen) focusSheet()
    } else {
      document.body.classList.remove("detail-modal")
      root.ControlRoomShell?.hideScrimIfIdle()
    }
  }

  /** Hide the surface and hand focus back to the node that opened it. */
  function close() {
    const node = surface()
    if (!node || node.dataset.open !== "true") return
    node.dataset.open = "false"
    document.body.classList.remove("detail-modal")
    root.ControlRoomShell?.hideScrimIfIdle()
    // Only restore focus if the trigger is still in the document: the fleet re-renders on
    // every poll, so the original button may already have been replaced.
    if (returnFocus instanceof HTMLElement && returnFocus.isConnected) returnFocus.focus({ preventScroll: true })
    returnFocus = null
  }

  /** Bind the surface's own controls and the board-side selection delegation. */
  function bindDetail() {
    // Delegation, not per-button binding: the boards re-render their controls on every poll.
    document.addEventListener("click", (event) => {
      const trigger = event.target instanceof Element ? event.target.closest(SELECTION_CONTROLS) : null
      if (trigger) open(trigger)
    })

    $("#detail-close")?.addEventListener("click", close)

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && $("#system-sheet")?.dataset.open !== "true") close()
      trapTab(event)
    })

    // app.js injects `.mobile-anchor` links (href="#transcript-panel") as a pre-sheet
    // fallback. Inside the sheet those anchors would jump the *page*; intercept them and
    // scroll the sheet body instead, which is what the operator means by "jump to transcript"
    // (design §3.1 replaced the anchor-jump chain with the sheet).
    document.addEventListener("click", (event) => {
      const anchor = event.target instanceof Element ? event.target.closest("a.mobile-anchor") : null
      if (!anchor || !anchor.getAttribute("href")?.startsWith("#")) return
      const target = document.querySelector(anchor.getAttribute("href"))
      if (!target) return
      event.preventDefault()
      open(anchor)
      if (typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "start", behavior: "smooth" })
    })

    // Crossing the breakpoint changes the surface's nature (sheet <-> column), so the modal
    // bookkeeping has to be re-evaluated rather than left in whichever state it was opened in.
    if (typeof root.matchMedia === "function") {
      const media = root.matchMedia(MODAL_QUERY)
      const onChange = () => {
        if (surface()?.dataset.open === "true") open(null)
        else {
          document.body.classList.remove("detail-modal")
          root.ControlRoomShell?.hideScrimIfIdle()
        }
      }
      if (typeof media.addEventListener === "function") media.addEventListener("change", onChange)
    }
  }

  const detail = { open, close, isModal }

  root.ControlRoomDetail = detail
  if (typeof module !== "undefined" && module.exports) module.exports = detail
  bindDetail()
})(typeof globalThis !== "undefined" ? globalThis : window, (typeof globalThis !== "undefined" ? globalThis : window).ControlRoomCore)
