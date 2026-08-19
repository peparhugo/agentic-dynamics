"use strict";

/**
 * Control Room — keyed list reconciliation and write-on-change DOM helpers.
 *
 * Four surfaces in this app render a polled list: the fleet matrix (5s), the supervisor flag
 * rail (5s), the recent design sessions (10s), and the Claude roster (10s). Every one of them
 * used to call `replaceChildren()` and rebuild the world, which on each poll destroyed keyboard
 * focus, restarted CSS animations, dropped text selections, broke scroll anchoring, and — via
 * the mutation records — gave assistive technology a reason to re-announce a region that had
 * not changed. "Calm under load" (design §1.1 principle 6, §2.5, §4.2) is the requirement; this
 * module is the mechanism.
 *
 * Two ideas, both deliberately small:
 *
 *  1. `reconcile()` — a list is identified by STABLE KEYS, not by position. Nodes are created
 *     once per key, updated in place, moved only when their position actually changes, and
 *     removed only when their key disappears.
 *  2. `setText` / `setHidden` / `setAttribute` — never write a value that is already there.
 *     Re-setting an attribute to its current value still queues a MutationRecord, so "write
 *     only on change" is what makes a no-op poll genuinely free.
 *
 * The module is pure DOM plumbing: it knows nothing about cells, flags, or sessions, and it
 * holds no state of its own — the caller owns the `entries` map, so it can keep whatever
 * per-row handles it needs alongside the node.
 *
 * Public surface (window.ControlRoomKeyedList):
 *   reconcile(options) -> {created, removed, moved}
 *   setText(node, text) / setHidden(node, hidden) / setAttribute(node, name, value)
 */
(function initControlRoomKeyedList(root) {
  /** Write `text` only when it differs from what the node already shows. */
  function setText(node, text) {
    if (!node) return false
    const value = String(text)
    if (node.textContent === value) return false
    node.textContent = value
    return true
  }

  /** Toggle the `hidden` attribute only on a real change. */
  function setHidden(node, hidden) {
    if (!node) return false
    const value = Boolean(hidden)
    if (node.hidden === value) return false
    node.hidden = value
    return true
  }

  /** Set an attribute only when its current value differs. */
  function setAttribute(node, name, value) {
    if (!node) return false
    const next = String(value)
    if (node.getAttribute(name) === next) return false
    node.setAttribute(name, next)
    return true
  }

  /** Set `className` only when it differs (a same-value write still invalidates style). */
  function setClassName(node, className) {
    if (!node) return false
    if (node.className === className) return false
    node.className = className
    return true
  }

  /**
   * Reconcile a container's children against an ordered list of keys.
   *
   * @param {object} options
   * @param {Element} options.container  parent element that holds the rows
   * @param {string[]} options.keys      desired keys, in the order they should appear
   * @param {Map} options.entries        caller-owned key -> entry map; each entry has `.node`
   * @param {function(string): object} options.create   build a new entry for a key
   * @param {function(object, string): void} options.update  refresh an existing entry in place
   * @param {function(object, string): void} [options.remove] custom teardown (defaults to
   *        removing the node); use it when a row owns a listener or timer
   * @returns {{created: number, removed: number, moved: number}} what actually changed, which
   *        callers and tests can assert on to prove a poll was a no-op
   *
   * The reorder pass walks the desired order against the live DOM order and moves a node only
   * when it is not already where it belongs, so a list whose order did not change performs
   * zero DOM writes without needing a separate "did the order change?" check.
   *
   * Untracked children (an empty-state paragraph, a static header) are tolerated: tracked nodes
   * are inserted before them, so a placeholder appended after the rows stays after the rows.
   */
  function reconcile(options) {
    const { container, keys, entries, create, update } = options
    const remove = options.remove || ((entry) => entry.node.remove())
    const report = { created: 0, removed: 0, moved: 0 }
    if (!container) return report

    // 1. Drop rows whose key is gone. Done first so the create pass below cannot collide with
    //    a stale node that happens to sit where a new one belongs.
    const wanted = new Set(keys)
    for (const [key, entry] of Array.from(entries)) {
      if (wanted.has(key)) continue
      remove(entry, key)
      entries.delete(key)
      report.removed += 1
    }

    // 2. Create missing rows (appended for now) and refresh every visible row. `update` is
    //    responsible for its own write-on-change discipline — this module cannot know which
    //    fields a row paints.
    for (const key of keys) {
      let entry = entries.get(key)
      if (!entry) {
        entry = create(key)
        entries.set(key, entry)
        container.appendChild(entry.node)
        report.created += 1
      }
      update(entry, key)
    }

    // 3. Put the rows in order with the minimum number of moves. `cursor` walks the live
    //    children; when the node already sits at the cursor, nothing is written and the cursor
    //    advances, so an unchanged order costs only the walk.
    let cursor = container.firstElementChild
    for (const key of keys) {
      const node = entries.get(key).node
      if (node === cursor) {
        cursor = cursor.nextElementSibling
        continue
      }
      container.insertBefore(node, cursor)
      report.moved += 1
    }
    return report
  }

  const keyedList = { reconcile, setText, setHidden, setAttribute, setClassName }

  root.ControlRoomKeyedList = keyedList
  if (typeof module !== "undefined" && module.exports) module.exports = keyedList
})(typeof globalThis !== "undefined" ? globalThis : window);
