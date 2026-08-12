"use strict"

const state = {
  cells: {},
  statusSource: null,
  eventSource: null,
}

const STATUS_COLORS = {
  queued: "#64748b",
  running: "#3b82f6",
  done: "#22c55e",
  failed: "#ef4444",
  timeout: "#f59e0b",
}

function $(sel) {
  return document.querySelector(sel)
}

function switchView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"))
  document
    .querySelectorAll("nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === name))
  $("#view-" + name).classList.add("active")
}

document.querySelectorAll("nav button").forEach((b) =>
  b.addEventListener("click", () => switchView(b.dataset.view)),
)

function renderMatrix() {
  const cells = state.cells
  const counts = {}
  for (const s of Object.values(cells)) counts[s] = (counts[s] || 0) + 1
  const total = Object.keys(cells).length
  const done = counts.done || 0
  const failed = counts.failed || 0
  const timeout = counts.timeout || 0
  const running = counts.running || 0
  const completed = done + failed + timeout

  $("#summary").innerHTML = `
    <div class="stat"><b>${total}</b> cells</div>
    <div class="stat running"><b>${running}</b> running</div>
    <div class="stat done"><b>${done}</b> done</div>
    <div class="stat failed"><b>${failed}</b> failed</div>
    <div class="stat timeout"><b>${timeout}</b> timeout</div>
    <div class="stat"><b>${completed}/${total}</b> completed</div>`

  const ids = Object.keys(cells).sort()
  if (ids.length === 0) {
    $("#matrix").innerHTML = '<p class="empty">No cells. Enqueue an experiment to begin.</p>'
    return
  }
  $("#matrix").innerHTML =
    '<div class="grid">' +
    ids
      .map((id) => {
        const st = cells[id]
        const color = STATUS_COLORS[st] || "#666"
        return `<div class="cell" style="--c:${color}" title="${id}">
          <div class="cell-status">${st}</div>
          <div class="cell-id">${id}</div>
        </div>`
      })
      .join("") +
    "</div>"
}

function populateSelect() {
  const sel = $("#cell-select")
  const current = sel.value
  const ids = Object.keys(state.cells).sort()
  sel.innerHTML = ids.map((id) => `<option value="${id}">${id}</option>`).join("")
  if (current && ids.includes(current)) sel.value = current
}

function loadMatrix() {
  fetch("/api/matrix")
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        $("#summary").innerHTML = `<p class="empty">${data.error}</p>`
        return
      }
      state.cells = data.cells || {}
      renderMatrix()
      populateSelect()
    })
    .catch(() => {})
}

function connectStatusStream() {
  if (state.statusSource) state.statusSource.close()
  state.statusSource = new EventSource("/api/status")
  state.statusSource.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      if (msg.cell_id && msg.status) {
        state.cells[msg.cell_id] = msg.status
        renderMatrix()
        populateSelect()
      }
    } catch (_) {}
  }
}

function formatEvent(obj) {
  const t = obj.type
  const part = obj.part || {}
  switch (t) {
    case "text":
      return `[text] ${part.text || ""}`
    case "reasoning":
      return `[reasoning] ${part.text || ""}`
    case "tool_use":
      return `[tool] ${part.tool || "?"} (${(part.state || {}).status || "?"})`
    case "step_start":
      return "[step-start]"
    case "step_finish": {
      const tk = part.tokens || {}
      return `[step-finish] in=${tk.input || 0} out=${tk.output || 0} $${part.cost ?? 0}`
    }
    default:
      return JSON.stringify(obj)
  }
}

function connectEventStream(cellId) {
  if (state.eventSource) state.eventSource.close()
  const pre = $("#transcript")
  pre.innerHTML = ""
  state.eventSource = new EventSource("/api/events/" + encodeURIComponent(cellId))
  state.eventSource.onmessage = (e) => {
    let text = e.data
    try {
      text = formatEvent(JSON.parse(e.data))
    } catch (_) {}
    const div = document.createElement("div")
    div.textContent = text
    pre.appendChild(div)
    while (pre.childNodes.length > 500) pre.removeChild(pre.firstChild)
    pre.scrollTop = pre.scrollHeight
  }
}

function loadRouting() {
  fetch("/api/routing")
    .then((r) => r.json())
    .then((data) => renderRouting(data))
    .catch(() => {
      $("#routing").innerHTML = '<p class="empty">Routing unavailable.</p>'
    })
}

function renderRouting(data) {
  const perTask = data.per_task || []
  const strategies = data.strategies || {}

  if (perTask.length === 0) {
    $("#routing").innerHTML =
      '<p class="empty">No routing data yet. Run experiments across multiple models first.</p>'
    return
  }

  const rows = perTask
    .map((t) => {
      const route = t.routing === "escalate" ? "escalate" : "default"
      const target = t.routing === "escalate" ? t.escalate_model : t.default_model
      return `<tr>
        <td class="mono">${t.task}</td>
        <td class="${route}">${route}</td>
        <td>${target || "?"}</td>
        <td>${t.best_correctness_model || "?"}</td>
        <td>${t.best_efficiency_model || "?"}</td>
      </tr>`
    })
    .join("")

  const stratRows = Object.entries(strategies)
    .map(([name, s]) => {
      const cost = s.total_cost ?? 0
      const corr = (s.avg_correctness ?? 0) * 100
      return `<tr>
        <td class="mono">${name}</td>
        <td>${s.n ?? 0}</td>
        <td>$${(cost || 0).toFixed(2)}</td>
        <td>${corr.toFixed(0)}%</td>
      </tr>`
    })
    .join("")

  $("#routing").innerHTML = `
    <h3>Per-task routing</h3>
    <table>
      <thead><tr><th>Task</th><th>Route</th><th>Target</th><th>Best correctness</th><th>Best efficiency</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <h3>Strategy simulation</h3>
    <table>
      <thead><tr><th>Strategy</th><th>N</th><th>Total cost</th><th>Avg correctness</th></tr></thead>
      <tbody>${stratRows}</tbody>
    </table>`
}

$("#cell-select").addEventListener("change", (e) => {
  if (e.target.value) connectEventStream(e.target.value)
})
$("#clear-transcript").addEventListener("click", () => {
  $("#transcript").innerHTML = ""
})

switchView("matrix")
loadMatrix()
connectStatusStream()
loadRouting()
setInterval(loadMatrix, 5000)
