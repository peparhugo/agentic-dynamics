#!/usr/bin/env python3
"""Deterministic rebuild of the Control Room parity inventory.

Why this file exists
--------------------
The UX-repair wave (`workflows/repository/control_room_ux_repair.yaml`) has one
hard rule: **no silent drops**. The facelift branch replaced the old room's
~235 panel/control ids with a 24-id resting screen and re-pointed the client at
two endpoints, while the server kept every route. A repair is only honest if it
can prove, item by item, what the old room offered and where each capability
goes.

This generator reads the OLD room from git (``main`` by default) — its
``index.html`` ids, its route registrations, and the endpoints its client
actually calls — and the CURRENT working tree, then emits
``parity_inventory.json``. Every extracted old id and route must appear in a
curated table below or the build FAILS LOUDLY, which is the mechanism that makes
"no silent drops" enforceable rather than aspirational.

Inputs (read-only):
    git show <ref>:apps/control_room/static/index.html
    git show <ref>:apps/control_room/routes/*.py  (+ server.py, routes/index.py)
    git show <ref>:apps/control_room/static/*.js
    apps/control_room/static/*        (current facelift)
    apps/control_room/routes/*.py     (current routes)

Output:
    experiments/research/control_room/parity_inventory.json

Run:
    python3 experiments/research/control_room/build_parity_inventory.py
    python3 experiments/research/control_room/build_parity_inventory.py --old-ref main
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths and constants
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # experiments/research/control_room -> repo root
OUT_PATH = HERE / "parity_inventory.json"

OLD_REF = "main"
OLD_INDEX = "apps/control_room/static/index.html"
OLD_JS_DIR = "apps/control_room/static"
OLD_ROUTE_FILES = [
    "apps/control_room/server.py",
    "apps/control_room/routes/index.py",
    "apps/control_room/routes/telemetry.py",
    "apps/control_room/routes/flags.py",
    "apps/control_room/routes/registry.py",
    "apps/control_room/routes/recording.py",
    "apps/control_room/routes/design_sessions.py",
    "apps/control_room/routes/claude_agents.py",
    "apps/control_room/routes/docs_health.py",
]
CUR_INDEX = ROOT / "apps" / "control_room" / "static" / "index.html"
CUR_JS_DIR = ROOT / "apps" / "control_room" / "static"
CUR_ROUTE_DIR = ROOT / "apps" / "control_room" / "routes"

#: The only three disposition values the repair campaign permits.
DISPOSITIONS = ("preserve", "re-house", "replace-with-reason")

# --------------------------------------------------------------------------- #
# The surface palette (u3 reconciliation).
#
# ``docs/research/control_room_ia.md`` §12–§15 places every old surface. The
# palette below is that placement as machine-readable ids: every item, endpoint,
# and capability record carries a ``surface`` drawn from this closed set, and the
# builder refuses any value outside it. This is what makes "every parity item is
# placed" a build-time fact rather than a prose claim; ``u5_gate_semantic_parity``
# then asserts each surface exists (and is non-empty) in the running room.
# --------------------------------------------------------------------------- #
SURFACES: dict[str, str] = {
    "R0": "System/trust bar (ON-G1, ON-G6)",
    "R1": "Attention inbox: R1a decision, R1b risk, R1c next (ON-G3, ON-G5)",
    "R2": "Run ledger (ON-G2)",
    "R3a": "Cost constraint annotation (ON-G4)",
    "R3b": "Health detail (worker/projection mirror)",
    "R3c": "Bounded composition (ON-G7)",
    "R4a": "Dock address/identity band",
    "R4b": "Dock per-worker event stream + action region",
    "R4c": "Dock evidence ladder",
    "R4d": "Dock step-timing region",
    "L-MONEY": "Money lens (spend/burn/history/leases)",
    "L-FLEET": "Fleet lens (full roster, filters, search, density)",
    "L-ATTENTION": "Attention lens (full inbox, all advisories)",
    "L-HEALTH": "Health/projection lens (per-projector detail)",
    "L-COMPOSITION": "Composition/performance lens",
    "L-WORKFORCE": "Workforce step-timing lens (aggregate by model)",
    "L-REGISTRY": "Canonical-lineage/registry destination (ON-D4)",
    "L-SESSIONS": "Sessions object type (design + Claude inspectors + search)",
    "QUEUE": "Queue control surface (enqueue/clear/reinterleave)",
    "DOCS": "Docs-health decision surface",
    "AUDIT": "Recording/decision audit surface (J7)",
    "SEARCH": "Global typed search / command accelerator",
    "SYSTEM": "System/help link (topology, architecture)",
    "A11Y": "Single polite live region (announcement policy)",
}

#: panel -> its canonical resting or drill-down surface.
PANEL_SURFACE: dict[str, str] = {
    "rail": "R0",
    "detail": "R4a",
    "transcript": "R4b",
    "cell": "R4b",
    "supervisor": "R1",
    "design": "L-SESSIONS",
    "claude": "L-SESSIONS",
    "fleet": "R2",
    "docs-health": "DOCS",
    "live-now": "R2",
    "status": "R3a",
    "flags": "R1",
    "sessions": "L-SESSIONS",
    "routing": "R4a",
    "system": "SEARCH",
    "registry": "L-REGISTRY",
    "queue": "QUEUE",
    "usage": "R3a",
    "announcer": "A11Y",
}

#: Per-id surface overrides where one element's home differs from its panel's.
ID_SURFACE: dict[str, str] = {
    "system-toggle": "SEARCH",
    "system-nav": "SEARCH",
    "destinations": "SEARCH",
    "burn-label": "L-MONEY",
    "burn-rate": "L-MONEY",
    "burn-trace": "L-MONEY",
    "registry-lineage": "L-REGISTRY",
    "registry-lineage-content": "L-REGISTRY",
    "supervisor-flag-list": "L-ATTENTION",
    "supervisor-steer": "R4b",
    "supervisor-interrupt": "R4b",
    "confirm-supervisor-interrupt": "R4b",
    "watch-button": "R4b",
    "copy-session": "R4a",
    "control-session": "R4a",
}

#: endpoint -> its target surface.
ENDPOINT_SURFACE: dict[str, str] = {
    "GET /": "SEARCH",
    "GET /api/matrix": "R2",
    "GET /api/status": "R2",
    "GET /api/projections": "R3b",
    "GET /api/events/<cell_id>": "R4b",
    "GET /api/routing": "R4a",
    "GET /api/subscription-usage": "R3a",
    "POST /api/experiments": "QUEUE",
    "POST /api/queue/reinterleave": "QUEUE",
    "GET /api/flags": "R1",
    "POST /api/flags/<session_id>/steer": "R4b",
    "POST /api/flags/<session_id>/interrupt": "R4b",
    "GET /api/registry": "L-REGISTRY",
    "GET /api/registry/<entity_id>": "L-REGISTRY",
    "GET /api/recording-audit": "AUDIT",
    "POST /api/recording-sweep/run": "AUDIT",
    "GET /api/docs-health": "DOCS",
    "POST /api/docs-health/approve": "DOCS",
    "GET /api/design-sessions": "L-SESSIONS",
    "POST /api/design-sessions": "L-SESSIONS",
    "GET /api/design-sessions/<portal_id>/spec": "L-SESSIONS",
    "POST /api/design-sessions/<portal_id>/input": "R4b",
    "POST /api/design-sessions/<portal_id>/interrupt": "R4b",
    "POST /api/design-sessions/<portal_id>/save": "L-SESSIONS",
    "POST /api/design-sessions/<portal_id>/run": "L-SESSIONS",
    "GET /api/claude-agents": "L-SESSIONS",
    "GET /api/claude-agents/<session_id>/logs": "R4b",
    "GET /api/claude-agents/daemon": "L-SESSIONS",
    "POST /api/claude-agents": "L-SESSIONS",
    "POST /api/claude-agents/<session_id>/stop": "R4b",
    "POST /api/claude-agents/<session_id>/respawn": "R4b",
    "POST /api/claude-agents/<session_id>/rm": "R4b",
    "POST /api/claude-agents/<session_id>/steer": "R4b",
    "POST /api/claude-agents/daemon/stop": "L-SESSIONS",
}

#: capability id -> its surface.
CAPABILITY_SURFACE: dict[str, str] = {
    "per-worker-event-stream": "R4b",
    "per-worker-actions": "R4b",
    "workforce-step-timings": "R4d",
    "boards": "R0",
    "burn-trace": "L-MONEY",
    "claude-agent-controls": "L-SESSIONS",
    "queue-controls": "QUEUE",
    "supervisor-controls": "R1",
    "design-controls": "L-SESSIONS",
    "cell-panel": "R4b",
}


# --------------------------------------------------------------------------- #
# The curated map: which panel owns each old id, its role, purpose, disposition,
# and target surface. Ids are grouped by the panel they lived in so the table is
# auditable in the same shape as the old DOM.
#
# ``__purpose__`` fields below are the PANEL purpose; a per-id purpose override
# lives in ``CONTROL_PURPOSES`` for the ids that are actionable controls.
# --------------------------------------------------------------------------- #

#: panel -> the old ids that belong to it (exhaustive; verified by the builder).
ID_PANEL: dict[str, list[str]] = {
    "rail": [
        "app-shell", "overall-state", "utc-clock", "theme-toggle", "system-toggle",
        "destinations", "system-nav",
    ],
    "detail": [
        "detail-surface", "detail-handle", "transcript-mode", "transcript-title",
        "selected-status", "selected-phase", "selected-stream-state", "selected-glance",
        "selected-cost", "selected-tokens", "detail-close", "scrim",
    ],
    "transcript": [
        "transcript-panel", "follow-button", "pause-button", "clear-button",
        "transcript-feed", "jump-live", "transcript-note",
    ],
    "cell": [
        "control-mode", "control-title", "ownership-badge", "cell-control-panel",
        "control-cell", "control-status", "control-stream", "control-session",
        "copy-session", "watch-button", "control-guidance",
    ],
    "supervisor": [
        "supervisor-control-panel", "supervisor-title", "supervisor-session-id",
        "supervisor-model", "supervisor-status", "supervisor-reason", "supervisor-review",
        "supervisor-activity", "supervisor-steer-form", "supervisor-steer-prompt",
        "supervisor-steer", "supervisor-steer-result", "supervisor-interrupt",
        "detach-supervisor", "supervisor-interrupt-door", "interrupt-door-title",
        "supervisor-confirmation-phrase", "supervisor-interrupt-confirmation",
        "cancel-supervisor-interrupt", "confirm-supervisor-interrupt",
        "supervisor-interrupt-result",
    ],
    "design": [
        "design-control-panel", "design-kind", "design-portal-id", "design-opencode-id",
        "design-session-model", "design-session-workdir", "design-draft-name",
        "design-revision", "validation-title", "validation-badge", "validation-summary",
        "validation-errors", "matrix-preview", "matrix-summary", "matrix-cells",
        "save-spec-form", "save-spec-name", "save-spec-button", "save-spec-result",
        "run-workflow-form", "run-goal", "run-model", "run-workdir", "run-backend",
        "run-timeout", "run-thinking-budget", "run-output-limit", "run-commit",
        "run-workflow-button", "run-workflow-result", "design-composer", "design-prompt",
        "send-design-input", "steer-design-input", "design-input-result",
        "interrupt-design", "detach-design",
    ],
    "claude": [
        "claude-agent-control-panel", "claude-agent-control-id",
        "claude-agent-control-status", "claude-agent-control-ownership",
        "claude-agent-control-model", "claude-agent-control-cwd",
        "claude-agent-transcript-note", "claude-agent-steer-form",
        "claude-agent-steer-prompt", "claude-agent-steer", "claude-agent-steer-result",
        "claude-agent-owned-controls", "claude-agent-stop", "claude-agent-respawn",
        "claude-agent-rm", "claude-agent-detach", "claude-agent-external-controls",
        "claude-agent-fetch-logs", "claude-agent-detach-external",
        "claude-agent-external-log", "claude-agent-action-result",
        "claude-agents", "claude-agents-title", "claude-agent-total",
        "new-claude-agent", "claude-agent-daemon-panel", "daemon-panel-title",
        "daemon-status", "daemon-pid", "daemon-end-sessions", "daemon-stop-button",
        "daemon-stop-result", "claude-agent-start-form", "claude-agent-task",
        "claude-agent-model", "claude-agent-advisor", "claude-agent-workdir",
        "cancel-claude-agent-start", "start-claude-agent", "claude-agent-start-result",
        "claude-agent-grid",
    ],
    "fleet": [
        "boards", "board-fleet", "fleet-title", "fleet-total", "matrix-age",
        "pipeline-stages", "cell-search", "density-toggle", "fleet-grid", "fleet-counts",
    ],
    "docs-health": [
        "docs-health", "docs-health-title", "docs-health-glyph", "docs-health-word",
        "docs-health-scanned", "docs-health-headline", "docs-health-axes",
        "docs-health-inventory", "docs-health-proposal", "docs-health-proposal-detail",
        "docs-health-approve-form", "docs-health-by", "docs-health-reason",
        "docs-health-approve-button", "docs-health-approve-result",
    ],
    "live-now": ["live-now", "live-now-title", "live-now-count", "live-now-list"],
    "status": [
        "board-status", "status-title", "spend-label", "reported-spend",
        "spend-provenance", "burn-label", "burn-rate", "burn-trace", "input-tokens",
        "output-tokens", "running-count", "redis-state",
    ],
    "flags": [
        "board-flags", "flags-title", "supervisor-source", "supervisor-count",
        "supervisor-rail", "supervisor-delay", "supervisor-flag-list",
    ],
    "sessions": [
        "board-sessions", "sessions-title", "design-launchers-title",
        "new-workflow-design", "new-experiment-design", "recent-designs-title",
        "recent-design-list", "design-start-form", "design-start-title",
        "design-intent-label", "design-intent", "design-model", "design-workdir",
        "cancel-design-start", "start-design-session", "design-start-result",
    ],
    "routing": [
        "board-routing", "routing-title", "routing-toggle", "routing-refresh",
        "routing-drawer", "routing-content",
    ],
    "system": ["system-sheet", "system-title", "system-close"],
    "registry": [
        "registry-title", "registry-toggle", "registry-refresh", "registry-drawer",
        "registry-filters", "registry-filter-type", "registry-filter-lifecycle",
        "registry-filter-since", "registry-content", "registry-lineage",
        "registry-lineage-content",
    ],
    "queue": [
        "queue-title", "enqueue-button", "clear-queue-button", "queue-clear-door",
        "queue-door-title", "queue-confirmation-phrase", "queue-clear-confirmation",
        "cancel-queue-clear", "confirm-queue-clear", "queue-result",
    ],
    "usage": ["usage-title", "usage-refresh", "usage-content"],
    "announcer": ["polite-status", "alert-status"],
}

#: panel -> {purpose, disposition, target, contract_ref, reason?}. The disposition
#: is the TARGET decision (what the repair should do); the builder independently
#: records what the facelift actually did via ``facelift``/``facelift_route``.
PANEL_META: dict[str, dict[str, str]] = {
    "rail": {
        "purpose": "Command rail: connection identity, clocks, theme, and System entry",
        "disposition": "re-house",
        "target": "R0 scope/truth + #theme-toggle; System contents become search/lenses",
        "contract_ref": "u0 DP1/DP8; u1 §1.4",
    },
    "detail": {
        "purpose": "Transversal detail sheet: selected object header, glance facts, and close/dismiss",
        "disposition": "re-house",
        "target": "R4 selection dock (docked ≥760px, sheet below)",
        "contract_ref": "u1 §5; u0 DP10",
    },
    "transcript": {
        "purpose": "Per-worker retained/live event transcript with follow, pause, clear, jump-to-live",
        "disposition": "re-house",
        "target": "R4 bounded attempt feed ([data-attempt-feed][data-feed-follow]) + /api/events/<cell_id>",
        "contract_ref": "u1 §3.2; u0 DP7",
    },
    "cell": {
        "purpose": "Cell/session control panel: attachment state, session identity, watch/detach/copy",
        "disposition": "re-house",
        "target": "R4 identity/lifecycle facts + attach/detach/copy address band",
        "contract_ref": "u1 §3.1.A; u0 DP2",
    },
    "supervisor": {
        "purpose": "Supervisor flag detail and the safe steer/interrupt actions for one flagged session",
        "disposition": "re-house",
        "target": "R1 advisory/decision item + R4 flag detail with safe action",
        "contract_ref": "u1 §3.1.E, §4; u0 DP4",
    },
    "design": {
        "purpose": "Design-session inspector: draft/validation, composer, save-spec, run-workflow, interrupt",
        "disposition": "re-house",
        "target": "Sessions object type + R4 design-session inspector",
        "contract_ref": "u1 §3.1.C, §5.1 ON-D3",
    },
    "claude": {
        "purpose": "Background claude session roster, daemon, start form, and ownership-aware controls",
        "disposition": "re-house",
        "target": "Sessions object type + R4 Claude-session inspector",
        "contract_ref": "u1 §3.1.B, §5.1 ON-D7",
    },
    "fleet": {
        "purpose": "Fleet roster: cell cards, counts, pipeline strip, search and density controls",
        "disposition": "re-house",
        "target": "R2 run ledger (+ R0/R3 annotations); slice features become lens controls",
        "contract_ref": "u0 DP1/DP7; u1 §1.4",
    },
    "docs-health": {
        "purpose": "Docs-drift health, axes, inventory, and the controller remediation approval",
        "disposition": "re-house",
        "target": "R1 decision / ON-G5; POST /api/docs-health/approve",
        "contract_ref": "u1 §3.1.F, §2.2",
    },
    "live-now": {
        "purpose": "Live now: runs whose last phase published inside the 10-minute window",
        "disposition": "re-house",
        "target": "R2 run ledger (live always visible; no duplicate list)",
        "contract_ref": "u0 §3 P6; control_room_ia.md §9 migration map",
    },
    "status": {
        "purpose": "Money/telemetry board: spend, rolling burn trace, tokens, running, Redis",
        "disposition": "re-house",
        "target": "R3a five money values + Money/trends lens (burn trace becomes a chart)",
        "contract_ref": "u0 DP5/DP7; u1 §3.4",
    },
    "flags": {
        "purpose": "Supervisor flags board: source/degraded state and the flag list",
        "disposition": "re-house",
        "target": "R1 advisory + persistent Flags view (ON-A5)",
        "contract_ref": "u1 §4",
    },
    "sessions": {
        "purpose": "Sessions board: design launchers, recent designs, and the create-design form",
        "disposition": "re-house",
        "target": "Sessions object type + global search classes",
        "contract_ref": "u1 §5.1",
    },
    "routing": {
        "purpose": "Routing board: model/strategy recommendation drawer",
        "disposition": "replace-with-reason",
        "reason": (
            "A peer board fragments one run decision across destinations; routing inputs "
            "belong beside the run that will use them (control_room_direction.md §4.3)."
        ),
        "target": "R4 run-context routing inputs (ON-D5)",
        "contract_ref": "u0 §3 P4/P8; u1 §6",
    },
    "system": {
        "purpose": "System overflow sheet: modal container for registry, queue, and usage",
        "disposition": "replace-with-reason",
        "reason": (
            "A modal overflow is not an information architecture; its contents become typed "
            "destinations, lenses, and search entries (control_room_direction.md §4.3)."
        ),
        "target": "Search + deliberate lenses; contents re-housed in R1/R3/Registry",
        "contract_ref": "u0 §3 P4; u1 §6",
    },
    "registry": {
        "purpose": "Registry: canonical records table, filters, and lineage",
        "disposition": "replace-with-reason",
        "reason": (
            "Canonical lineage is what justifies a decision; burying it behind a gear makes "
            "the evidence hardest to reach when it is most needed (r0 M4). It becomes an "
            "evidence destination, not an overflow drawer."
        ),
        "target": "Canonical-lineage evidence destination (ON-D4)",
        "contract_ref": "u0 §3 P4; u1 §5.1 ON-D4, §6",
    },
    "queue": {
        "purpose": "Queue controls: enqueue, clear (typed door), and the confirmation phrase",
        "disposition": "re-house",
        "target": "§3.1.D queue controls (POST /api/experiments)",
        "contract_ref": "u1 §3.1.D",
    },
    "usage": {
        "purpose": "Subscription usage: provider windows, DeepSeek wallet, reserved leases",
        "disposition": "re-house",
        "target": "R3a five values + R3b/Money lens (GET /api/subscription-usage)",
        "contract_ref": "u0 DP5; u1 §3.4, §6",
    },
    "announcer": {
        "purpose": "Screen-reader live regions for polite/assertive status",
        "disposition": "re-house",
        "target": "#announcer single polite transition-only live region",
        "contract_ref": "u1 §4.3",
    },
}

#: ids whose purpose must be stated as an action, not a panel role.
CONTROL_PURPOSES: dict[str, str] = {
    # rail
    "theme-toggle": "Toggle the dark/light theme",
    "system-toggle": "Open the System overflow sheet",
    "system-nav": "Move focus to a System section",
    # detail / transcript
    "detail-handle": "Mobile drag handle to dismiss the detail sheet",
    "detail-close": "Close the detail surface",
    "follow-button": "Toggle follow on the transcript feed",
    "pause-button": "Pause or resume the live transcript feed",
    "clear-button": "Clear the local transcript view (browser only)",
    "jump-live": "Jump the transcript feed back to the live edge",
    # cell
    "copy-session": "Copy the observed OpenCode session id",
    "watch-button": "Attach to / detach from the selected cell's live event stream",
    # supervisor
    "supervisor-steer-form": "Compose a steer prompt for the flagged session",
    "supervisor-steer-prompt": "Steer prompt text area",
    "supervisor-steer": "Send the steer prompt to the flagged session",
    "supervisor-interrupt": "Open the interrupt typed-confirmation door",
    "detach-supervisor": "Detach from the flag's transcript",
    "supervisor-interrupt-door": "One-way-door confirmation for interrupt",
    "supervisor-interrupt-confirmation": "Type INTERRUPT to enable the confirm control",
    "cancel-supervisor-interrupt": "Cancel the interrupt door",
    "confirm-supervisor-interrupt": "Confirm the irreversible interrupt",
    # design
    "save-spec-form": "Save the validated draft as a spec file",
    "save-spec-name": "Spec basename for saving",
    "save-spec-button": "Submit the save-spec form",
    "run-workflow-form": "Launch a workflow from the approved worktree",
    "run-goal": "Goal prompt for the workflow run",
    "run-model": "Model id for the workflow run",
    "run-workdir": "Approved worktree selector",
    "run-backend": "Backend selector (auto/opencode/claude_cli)",
    "run-timeout": "Per-phase timeout in seconds",
    "run-thinking-budget": "Thinking token budget",
    "run-output-limit": "Output token limit",
    "run-commit": "Commit successful phases",
    "run-workflow-button": "Submit the workflow run (spends budget)",
    "design-composer": "Compose a change request for the design session",
    "design-prompt": "Design change prompt text area",
    "send-design-input": "Queue the design change",
    "steer-design-input": "Steer the design session with the change",
    "interrupt-design": "Interrupt the design session",
    "detach-design": "Detach from the design session",
    # claude controls
    "claude-agent-steer-form": "Adjust-and-continue (steer) form for an owned session",
    "claude-agent-steer-prompt": "Steer prompt for the owned session",
    "claude-agent-steer": "Steer the owned session (stop + resume; new id)",
    "claude-agent-owned-controls": "Owned-session action group",
    "claude-agent-stop": "Stop the owned claude session (conversation preserved)",
    "claude-agent-respawn": "Respawn the owned session with its conversation",
    "claude-agent-rm": "Remove the owned session from the roster",
    "claude-agent-detach": "Detach from the owned session",
    "claude-agent-external-controls": "External-session read-only action group",
    "claude-agent-fetch-logs": "Fetch the external session's log tail",
    "claude-agent-detach-external": "Detach from the external session",
    # claude roster
    "new-claude-agent": "Reveal / start a new background session form",
    "daemon-end-sessions": "Also end every hosted session (keep_workers:false)",
    "daemon-stop-button": "Stop the claude daemon",
    "claude-agent-start-form": "Start a background claude session",
    "claude-agent-task": "Task prompt for the new session",
    "claude-agent-model": "Model for the new session",
    "claude-agent-advisor": "Advisor model for the new session",
    "claude-agent-workdir": "Approved workdir for the new session",
    "cancel-claude-agent-start": "Cancel the start-session form",
    "start-claude-agent": "Submit the start-session form",
    # fleet
    "cell-search": "Filter the fleet by cell id",
    "density-toggle": "Toggle compact/comfortable fleet density",
    # docs-health
    "docs-health-approve-form": "Approve and dispatch a docs remediation proposal",
    "docs-health-by": "Signer of the docs approval",
    "docs-health-reason": "Optional reason for the docs approval",
    "docs-health-approve-button": "Submit the docs approval",
    # sessions
    "new-workflow-design": "Start a workflow design session",
    "new-experiment-design": "Start an experiment design session",
    "design-start-form": "Create a new design session",
    "design-intent": "Design intent prompt",
    "design-model": "Model for the design session",
    "design-workdir": "Approved workdir for the design session",
    "cancel-design-start": "Cancel the create-design form",
    "start-design-session": "Submit the create-design form",
    # routing
    "routing-toggle": "Show/hide the routing drawer",
    "routing-refresh": "Refresh routing recommendations",
    # system
    "system-close": "Close the System sheet",
    # registry
    "registry-toggle": "Show/hide the registry drawer",
    "registry-refresh": "Refresh the registry table",
    "registry-filters": "Filter the registry table",
    "registry-filter-type": "Filter registry records by record type",
    "registry-filter-lifecycle": "Filter registry records by lifecycle",
    "registry-filter-since": "Filter registry records since a timestamp",
    # queue
    "enqueue-button": "Enqueue experiments (POST /api/experiments action=enqueue)",
    "clear-queue-button": "Open the clear-queue typed door",
    "queue-clear-door": "One-way-door confirmation for clearing the queue",
    "queue-clear-confirmation": "Type CLEAR QUEUE to enable the confirm control",
    "cancel-queue-clear": "Cancel the clear-queue door",
    "confirm-queue-clear": "Confirm clearing all queued work",
    # usage
    "usage-refresh": "Refresh subscription usage (force provider refetch)",
}

#: control id -> the endpoint it calls in the old client (for feed/action trace).
CONTROL_ENDPOINTS: dict[str, str] = {
    "watch-button": "GET /api/events/<cell_id>",
    "copy-session": "",
    "supervisor-steer": "POST /api/flags/<session_id>/steer",
    "confirm-supervisor-interrupt": "POST /api/flags/<session_id>/interrupt",
    "save-spec-button": "POST /api/design-sessions/<portal_id>/save",
    "run-workflow-button": "POST /api/design-sessions/<portal_id>/run",
    "send-design-input": "POST /api/design-sessions/<portal_id>/input",
    "steer-design-input": "POST /api/design-sessions/<portal_id>/input",
    "interrupt-design": "POST /api/design-sessions/<portal_id>/interrupt",
    "start-design-session": "POST /api/design-sessions",
    "start-claude-agent": "POST /api/claude-agents",
    "claude-agent-stop": "POST /api/claude-agents/<session_id>/stop",
    "claude-agent-respawn": "POST /api/claude-agents/<session_id>/respawn",
    "claude-agent-rm": "POST /api/claude-agents/<session_id>/rm",
    "claude-agent-steer": "POST /api/claude-agents/<session_id>/steer",
    "claude-agent-fetch-logs": "GET /api/claude-agents/<session_id>/logs",
    "daemon-stop-button": "POST /api/claude-agents/daemon/stop",
    "new-workflow-design": "POST /api/design-sessions",
    "new-experiment-design": "POST /api/design-sessions",
    "enqueue-button": "POST /api/experiments",
    "confirm-queue-clear": "POST /api/experiments",
    "docs-health-approve-button": "POST /api/docs-health/approve",
    "routing-refresh": "GET /api/routing",
    "registry-refresh": "GET /api/registry",
    "usage-refresh": "GET /api/subscription-usage",
}

#: endpoint -> purpose + disposition + target. Every old route must appear.
ENDPOINT_META: dict[str, dict[str, str]] = {
    "GET /": {
        "purpose": "Serve the single-page Control Room shell",
        "disposition": "preserve",
        "target": "index.html",
    },
    "GET /api/matrix": {
        "purpose": "Fleet matrix snapshot: cells, telemetry, phases, projections",
        "disposition": "re-house",
        "target": "R2 roster + R0/R3 via /api/glance",
    },
    "GET /api/status": {
        "purpose": "SSE stream of all cell status transitions",
        "disposition": "re-house",
        "target": "R2 row-status transitions via /api/events",
    },
    "GET /api/projections": {
        "purpose": "Per-projection watermark report (registry/chroma/neo4j/ledger health)",
        "disposition": "re-house",
        "target": "R0 system/trust + R3b detail (render it — r0 M2)",
    },
    "GET /api/events/<cell_id>": {
        "purpose": "Per-cell SSE: replay retained log, replay_complete boundary, then live events",
        "disposition": "re-house",
        "target": "R4 per-worker event stream, one at a time (u1 §3.2)",
    },
    "GET /api/routing": {
        "purpose": "Model/strategy routing recommendation",
        "disposition": "replace-with-reason",
        "target": "R4 run-context routing inputs (ON-D5)",
    },
    "GET /api/subscription-usage": {
        "purpose": "Provider windows + DeepSeek wallet + reserved lease admission board",
        "disposition": "re-house",
        "target": "R3a five money values + R3b/Money lens",
    },
    "POST /api/experiments": {
        "purpose": "Enqueue or clear the experiment queue (spawns enqueue.py)",
        "disposition": "re-house",
        "target": "§3.1.D queue controls",
    },
    "POST /api/queue/reinterleave": {
        "purpose": "Re-interleave story_jobs round-robin across providers",
        "disposition": "re-house",
        "target": "§3.1.D queue controls (render it — r0 M11)",
    },
    "GET /api/flags": {
        "purpose": "Newest retained supervisor assessments with review metadata",
        "disposition": "re-house",
        "target": "R1 advisory + persistent Flags view",
    },
    "POST /api/flags/<session_id>/steer": {
        "purpose": "Admit a human steer prompt to one flagged session",
        "disposition": "re-house",
        "target": "R1/R4 safe action (u1 §3.1.A/E)",
    },
    "POST /api/flags/<session_id>/interrupt": {
        "purpose": "Interrupt one flagged session after exact confirmation",
        "disposition": "re-house",
        "target": "R1/R4 safe action behind a typed door (u1 §3.1.A/E)",
    },
    "GET /api/registry": {
        "purpose": "Canonical registry records with filters",
        "disposition": "replace-with-reason",
        "target": "Canonical-lineage evidence destination (ON-D4)",
    },
    "GET /api/registry/<entity_id>": {
        "purpose": "One entity's lineage (supersession / causes)",
        "disposition": "replace-with-reason",
        "target": "Canonical-lineage evidence destination (ON-D4)",
    },
    "GET /api/recording-audit": {
        "purpose": "Decision-record coverage audit",
        "disposition": "re-house",
        "target": "Audit surface (J7) + decision-receipt coverage (render it — r0 M12)",
    },
    "POST /api/recording-sweep/run": {
        "purpose": "One-click decision-record backfill sweep",
        "disposition": "re-house",
        "target": "Audit surface (J7) (render it — r0 M12)",
    },
    "GET /api/docs-health": {
        "purpose": "Docs-drift health across four axes + remediation proposal",
        "disposition": "re-house",
        "target": "R1 decision / ON-G5",
    },
    "POST /api/docs-health/approve": {
        "purpose": "Approve (and optionally dispatch) a docs remediation proposal",
        "disposition": "re-house",
        "target": "R1 decision / ON-G5 (u1 §3.1.F)",
    },
    "GET /api/design-sessions": {
        "purpose": "List design sessions and their draft state",
        "disposition": "re-house",
        "target": "Sessions object type + search",
    },
    "POST /api/design-sessions": {
        "purpose": "Create a workflow/experiment design session",
        "disposition": "re-house",
        "target": "Sessions object type (u1 §3.1.C)",
    },
    "GET /api/design-sessions/<portal_id>/spec": {
        "purpose": "Read a design session's draft spec and validation",
        "disposition": "re-house",
        "target": "R4 design-session inspector",
    },
    "POST /api/design-sessions/<portal_id>/input": {
        "purpose": "Send or steer a design change",
        "disposition": "re-house",
        "target": "R4 design composer (u1 §3.1.C)",
    },
    "POST /api/design-sessions/<portal_id>/interrupt": {
        "purpose": "Interrupt a design session",
        "disposition": "re-house",
        "target": "R4 design controls (u1 §3.1.C)",
    },
    "POST /api/design-sessions/<portal_id>/save": {
        "purpose": "Save a validated draft as a spec file",
        "disposition": "re-house",
        "target": "R4 design save (u1 §3.1.C)",
    },
    "POST /api/design-sessions/<portal_id>/run": {
        "purpose": "Launch a workflow from the design session",
        "disposition": "re-house",
        "target": "R4 design run (u1 §3.1.C)",
    },
    "GET /api/claude-agents": {
        "purpose": "Background claude session roster with ownership",
        "disposition": "re-house",
        "target": "Sessions object type (u1 §3.1.B)",
    },
    "GET /api/claude-agents/<session_id>/logs": {
        "purpose": "Read a background session's log tail",
        "disposition": "re-house",
        "target": "R4 Claude-session inspector log tail",
    },
    "GET /api/claude-agents/daemon": {
        "purpose": "Claude daemon status and PID",
        "disposition": "re-house",
        "target": "Sessions object type / R4 Claude inspector",
    },
    "POST /api/claude-agents": {
        "purpose": "Start a background claude session",
        "disposition": "re-house",
        "target": "R4 Claude start (u1 §3.1.B)",
    },
    "POST /api/claude-agents/<session_id>/stop": {
        "purpose": "Stop an owned background session (conversation preserved)",
        "disposition": "re-house",
        "target": "R4 Claude owned controls",
    },
    "POST /api/claude-agents/<session_id>/respawn": {
        "purpose": "Respawn an owned session with its conversation",
        "disposition": "re-house",
        "target": "R4 Claude owned controls",
    },
    "POST /api/claude-agents/<session_id>/rm": {
        "purpose": "Remove an owned session from the roster",
        "disposition": "re-house",
        "target": "R4 Claude owned controls",
    },
    "POST /api/claude-agents/<session_id>/steer": {
        "purpose": "Steer an owned session (stop + resume under a new id)",
        "disposition": "re-house",
        "target": "R4 Claude owned controls",
    },
    "POST /api/claude-agents/daemon/stop": {
        "purpose": "Stop the claude daemon (fleet-wide, severe)",
        "disposition": "re-house",
        "target": "R4 Claude daemon control behind a typed door",
    },
}

#: The named capability surfaces the repair explicitly requires. Each is a set of
#: old ids (+ endpoints) or an explicit "absent in the old room" note. This is the
#: block the task names directly: event stream/actions per worker, workforce step
#: timings, boards, burn trace, claude-agent, queue/supervisor/design controls,
#: and cell panel.
CAPABILITIES: list[dict[str, object]] = [
    {
        "id": "per-worker-event-stream",
        "purpose": "Replay + live per-cell event stream with follow/pause/clear/jump",
        "member_ids": ["transcript-panel", "transcript-feed", "follow-button",
                       "pause-button", "clear-button", "jump-live", "transcript-note",
                       "transcript-mode", "transcript-title"],
        "member_endpoints": ["GET /api/events/<cell_id>", "GET /api/status"],
        "disposition": "re-house",
        "target": "R4 bounded attempt feed, one stream at a time (u1 §3.2)",
        "contract_ref": "u1 §3.2; u0 DP7",
    },
    {
        "id": "per-worker-actions",
        "purpose": "Per-cycle/per-session controls: attach/detach/copy, steer, interrupt, watch",
        "member_ids": ["watch-button", "copy-session", "control-mode", "control-title",
                       "ownership-badge", "supervisor-steer", "supervisor-interrupt",
                       "detach-supervisor"],
        "member_endpoints": ["POST /api/flags/<session_id>/steer",
                             "POST /api/flags/<session_id>/interrupt"],
        "disposition": "re-house",
        "target": "R4 action band + R1 safe action (u1 §3.1.A/E)",
        "contract_ref": "u1 §3.1; u0 DP4",
    },
    {
        "id": "workforce-step-timings",
        "purpose": ("Step/attempt timing for the live workforce: queue wait, service time, "
                    "first-token latency, duration, retries, tokens by answer/explanation"),
        "member_ids": ["selected-phase", "selected-cost", "selected-tokens",
                       "transcript-feed"],
        "member_endpoints": [],
        "disposition": "re-house",
        "added": True,
        "note": ("Absent as a dedicated surface in BOTH rooms; the old transcript carried only "
                 "per-event cost/tokens. The data exists on the ledger AttemptRecord and "
                 "StepAttemptRecord; the repair must assemble it into a named timing view."),
        "target": "R4 per-attempt timing + R3b workforce timing aggregate (u1 §3.3)",
        "contract_ref": "u1 §3.3; u0 §2 J4 / §3 P3 (r0 A4)",
    },
    {
        "id": "boards",
        "purpose": "Five destination boards (Fleet, Status, Flags, Sessions, Routing)",
        "member_ids": ["boards", "board-fleet", "board-status", "board-flags",
                       "board-sessions", "board-routing"],
        "member_endpoints": ["GET /api/matrix", "GET /api/flags", "GET /api/design-sessions",
                             "GET /api/claude-agents", "GET /api/routing"],
        "disposition": "re-house",
        "target": "R0/R1/R2/R3 regions + deliberate lenses (no peer navigation)",
        "contract_ref": "control_room_ia.md §9 migration map",
    },
    {
        "id": "burn-trace",
        "purpose": "Rolling 60s reported-cost burn rate with a full-width sparkline trace",
        "member_ids": ["burn-label", "burn-rate", "burn-trace"],
        "member_endpoints": [],
        "disposition": "re-house",
        "target": "Money/trends lens (time-series chart, one scale)",
        "contract_ref": "u0 DP5/DP7; u1 §3.4",
    },
    {
        "id": "claude-agent-controls",
        "purpose": "Background claude roster, daemon, start form, and ownership-aware controls",
        "member_ids": ["claude-agents", "claude-agents-title", "claude-agent-total",
                       "new-claude-agent", "claude-agent-daemon-panel", "daemon-status",
                       "daemon-pid", "daemon-stop-button", "claude-agent-start-form",
                       "claude-agent-control-panel", "claude-agent-stop",
                       "claude-agent-respawn", "claude-agent-rm", "claude-agent-steer",
                       "claude-agent-fetch-logs", "claude-agent-grid"],
        "member_endpoints": ["GET /api/claude-agents", "GET /api/claude-agents/daemon",
                             "POST /api/claude-agents", "POST /api/claude-agents/<session_id>/stop",
                             "POST /api/claude-agents/<session_id>/respawn",
                             "POST /api/claude-agents/<session_id>/rm",
                             "POST /api/claude-agents/<session_id>/steer",
                             "POST /api/claude-agents/daemon/stop"],
        "disposition": "re-house",
        "target": "Sessions object type + R4 Claude-session inspector (u1 §3.1.B)",
        "contract_ref": "u1 §3.1.B, §5.1 ON-D7",
    },
    {
        "id": "queue-controls",
        "purpose": "Enqueue, clear (typed door), and the confirmation phrase",
        "member_ids": ["queue-title", "enqueue-button", "clear-queue-button",
                       "queue-clear-door", "queue-clear-confirmation",
                       "confirm-queue-clear", "queue-result"],
        "member_endpoints": ["POST /api/experiments"],
        "disposition": "re-house",
        "target": "§3.1.D queue controls",
        "contract_ref": "u1 §3.1.D",
    },
    {
        "id": "supervisor-controls",
        "purpose": "Flags board + flagged-session steer/interrupt with the typed door",
        "member_ids": ["board-flags", "flags-title", "supervisor-source", "supervisor-count",
                       "supervisor-rail", "supervisor-delay", "supervisor-flag-list",
                       "supervisor-control-panel", "supervisor-steer",
                       "supervisor-interrupt", "supervisor-interrupt-door"],
        "member_endpoints": ["GET /api/flags", "POST /api/flags/<session_id>/steer",
                             "POST /api/flags/<session_id>/interrupt"],
        "disposition": "re-house",
        "target": "R1 advisory/decision + R4 flag detail (u1 §3.1.E, §4)",
        "contract_ref": "u1 §3.1.E, §4; u0 DP4",
    },
    {
        "id": "design-controls",
        "purpose": "Design launchers, create form, composer, save-spec, run-workflow, interrupt",
        "member_ids": ["board-sessions", "design-launchers-title", "new-workflow-design",
                       "new-experiment-design", "recent-design-list", "design-start-form",
                       "design-control-panel", "design-composer", "save-spec-form",
                       "run-workflow-form", "interrupt-design", "detach-design"],
        "member_endpoints": ["GET /api/design-sessions", "POST /api/design-sessions",
                             "POST /api/design-sessions/<portal_id>/input",
                             "POST /api/design-sessions/<portal_id>/interrupt",
                             "POST /api/design-sessions/<portal_id>/save",
                             "POST /api/design-sessions/<portal_id>/run"],
        "disposition": "re-house",
        "target": "Sessions object type + R4 design inspector (u1 §3.1.C)",
        "contract_ref": "u1 §3.1.C, §5.1 ON-D3",
    },
    {
        "id": "cell-panel",
        "purpose": "Selected cell fact sheet: status, stream, session id, watch/detach",
        "member_ids": ["cell-control-panel", "control-mode", "control-title",
                       "ownership-badge", "control-cell", "control-status",
                       "control-stream", "control-session", "copy-session",
                       "watch-button", "control-guidance"],
        "member_endpoints": ["GET /api/events/<cell_id>"],
        "disposition": "re-house",
        "target": "R4 identity/lifecycle facts + attach/detach/copy (u1 §3.1.A)",
        "contract_ref": "u1 §3.1.A; u0 DP2",
    },
]


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def _git_show(ref: str, path: str) -> str:
    """Return the committed text of ``path`` at ``ref`` (empty string when absent)."""
    try:
        return subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return ""


def extract_ids(html: str) -> dict[str, str]:
    """Map each unique ``id="..."`` in ``html`` to its tag name (first occurrence wins)."""
    out: dict[str, str] = {}
    for m in re.finditer(r"<(\w+)([^>]*?)\bid=\"([^\"]+)\"", html):
        out.setdefault(m.group(3), m.group(1))
    return out


def extract_routes(source: str) -> list[str]:
    """Extract ``METHOD /path`` route registrations from a Python source file.

    Matches ``app.get("...")`` / ``app.post("...")`` and the ``@app.get(...)``
    decorator form; ignores non-route ``.get("KEY")`` calls (dict/env access) by
    requiring the ``app.`` receiver.
    """
    routes: list[str] = []
    for m in re.finditer(r"app\.(get|post)\(\s*[\"']([^\"']+)[\"']", source):
        routes.append(f"{m.group(1).upper()} {m.group(2)}")
    return routes


def extract_feeds(js: str) -> set[str]:
    """Return the API paths a JS client references as string literals.

    This is deliberately a literal scan rather than a ``fetch(``/``EventSource(``
    scan: the old room built its per-cell stream URL inside a multi-line
    ``core.replaceEventSource(...)`` call (``app.js:1756``), so the URL is not the
    first argument after the constructor name. Query strings are dropped and
    ``${...}`` template segments are normalised to ``<...>`` so a feed can be
    matched to its route pattern.
    """
    feeds: set[str] = set()
    for m in re.finditer(r"[\"'`](/api/[^\"'`]*)[\"'`]", js):
        raw = m.group(1).split("?")[0]
        raw = re.sub(r"\$\{[^}]*\}", "<...>", raw)
        if raw.startswith("/api"):
            feeds.add(raw)
    return feeds


def _normalise_route(path: str) -> str:
    """Normalise a path so ``/api/.../<....>`` and ``/api/.../<id>`` match."""
    return re.sub(r"<[^>]+>", "<...>", path)


def sha256_text(text: str) -> str:
    """Content hash for provenance (stable across line-ending differences)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #
#: Per-id overrides of the panel default. Used where a single id's target decision
#: differs from its panel's (e.g. the one id the facelift actually kept as-is).
ID_OVERRIDES: dict[str, dict[str, str]] = {
    "theme-toggle": {
        "disposition": "preserve",
        "target": "#theme-toggle (token-driven dark/light theme)",
        "contract_ref": "u0 DP8",
    },
}

_ACTION_TAGS = {"button", "input", "select", "textarea", "form", "details"}
_VALUE_TAGS = {"output", "pre", "code"}
_REGION_TAGS = {"section", "aside", "div", "nav", "main"}
_MARK_TAGS = {"svg"}


def kind_for(tag: str) -> str:
    """Classify an element into the inventory's coarse kind vocabulary."""
    if tag in _ACTION_TAGS:
        return "control"
    if tag in _VALUE_TAGS:
        return "value"
    if tag in _REGION_TAGS:
        return "region"
    if tag in _MARK_TAGS:
        return "mark"
    return "field"


def build_items(old_ids: dict[str, str], cur_ids: set[str]) -> list[dict[str, object]]:
    """One record per old id: panel, kind, purpose, facelift status, disposition, target."""
    panel_of: dict[str, str] = {}
    for panel, ids in ID_PANEL.items():
        for i in ids:
            panel_of[i] = panel

    # Coverage: every extracted old id must be mapped, and every mapped id must exist.
    mapped = set(panel_of)
    extracted = set(old_ids)
    missing_from_table = sorted(extracted - mapped)
    if missing_from_table:
        raise SystemExit(
            "PARITY BUILD FAILED — extracted old ids absent from ID_PANEL:\n  "
            + "\n  ".join(missing_from_table)
        )
    stale_in_table = sorted(mapped - extracted)
    if stale_in_table:
        raise SystemExit(
            "PARITY BUILD FAILED — ID_PANEL lists ids not in the old index.html:\n  "
            + "\n  ".join(stale_in_table)
        )

    items: list[dict[str, object]] = []
    for i in sorted(extracted):
        panel = panel_of[i]
        meta = PANEL_META[panel]
        override = ID_OVERRIDES.get(i, {})
        tag = old_ids[i]
        record: dict[str, object] = {
            "id": i,
            "kind": kind_for(tag),
            "panel": panel,
            "old_tag": tag,
            "old_ref": f"{OLD_INDEX} (main) #{i}",
            "purpose": CONTROL_PURPOSES.get(i) or f"{meta['purpose']} — {kind_for(tag)}",
            "surface": ID_SURFACE.get(i, PANEL_SURFACE[panel]),
            "facelift": "present" if i in cur_ids else "dropped",
            "disposition": override.get("disposition", meta["disposition"]),
            "target": override.get("target", meta["target"]),
            "contract_ref": override.get("contract_ref", meta["contract_ref"]),
        }
        if i in CONTROL_ENDPOINTS and CONTROL_ENDPOINTS[i]:
            record["old_endpoint"] = CONTROL_ENDPOINTS[i]
        reason = override.get("reason") or meta.get("reason")
        if reason:
            record["disposition_reason"] = reason
        items.append(record)
    return items


def build_endpoints(
    old_routes: list[str], cur_routes: set[str], old_feeds: set[str], cur_feeds: set[str]
) -> list[dict[str, object]]:
    """One record per old route; marks route survival and consumer status."""
    unmatched = [r for r in old_routes if r not in ENDPOINT_META]
    if unmatched:
        raise SystemExit(
            "PARITY BUILD FAILED — old routes absent from ENDPOINT_META:\n  "
            + "\n  ".join(unmatched)
        )
    norm_feeds = {_normalise_route(f) for f in old_feeds}
    norm_cur = {_normalise_route(f) for f in cur_feeds}
    out: list[dict[str, object]] = []
    for route in sorted(set(old_routes)):
        meta = ENDPOINT_META[route]
        route_norm = _normalise_route(route.split(" ", 1)[1])
        record: dict[str, object] = {
            "id": route,
            "kind": "endpoint",
            "purpose": meta["purpose"],
            "surface": ENDPOINT_SURFACE[route],
            "old_ref": "apps/control_room/routes/*.py (main)",
            "old_consumers": sorted(
                {_normalise_route(f) for f in old_feeds if _normalise_route(f) == route_norm}
            ),
            "facelift_route": "present" if route in cur_routes else "absent",
            "facelift_consumer": (
                "wired" if route_norm in norm_cur else "absent"
            ),
            "disposition": meta["disposition"],
            "target": meta["target"],
        }
        out.append(record)
    return out


def build_capabilities(cur_ids: set[str], cur_routes: set[str]) -> list[dict[str, object]]:
    """Emit the named capability surfaces, annotating facelift survival per member."""
    out: list[dict[str, object]] = []
    for cap in CAPABILITIES:
        members = list(cap.get("member_ids", []))  # type: ignore[arg-type]
        present = [m for m in members if m in cur_ids]
        dropped = [m for m in members if m not in cur_ids]
        endpoints = list(cap.get("member_endpoints", []))  # type: ignore[arg-type]
        record = dict(cap)
        record["surface"] = CAPABILITY_SURFACE[str(cap["id"])]
        record["facelift_members_present"] = present
        record["facelift_members_dropped"] = dropped
        record["facelift_endpoints_present"] = [e for e in endpoints if e in cur_routes]
        record["facelift_endpoints_absent"] = [e for e in endpoints if e not in cur_routes]
        out.append(record)
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def build(old_ref: str) -> dict[str, object]:
    """Assemble the whole inventory dict from the old ref and the working tree."""
    old_html = _git_show(old_ref, OLD_INDEX)
    if not old_html:
        raise SystemExit(f"no {OLD_INDEX} at ref {old_ref!r}")
    old_ids = extract_ids(old_html)

    old_js = "\n".join(_git_show(old_ref, f"{OLD_JS_DIR}/{p}") for p in
                       sorted({Path(p).name for p in _git_list(old_ref, OLD_JS_DIR, ".js")}))
    old_routes: list[str] = []
    for path in OLD_ROUTE_FILES:
        old_routes.extend(extract_routes(_git_show(old_ref, path)))

    old_feeds = extract_feeds(old_js)

    cur_html = CUR_INDEX.read_text(encoding="utf-8")
    cur_ids = set(extract_ids(cur_html))
    cur_routes: set[str] = set()
    for path in sorted(CUR_ROUTE_DIR.glob("*.py")):
        cur_routes.update(extract_routes(path.read_text(encoding="utf-8")))
    cur_routes.update(extract_routes((ROOT / "apps" / "control_room" / "server.py").read_text(encoding="utf-8")))
    cur_js = "\n".join(p.read_text(encoding="utf-8") for p in sorted(CUR_JS_DIR.glob("*.js")))
    cur_feeds = extract_feeds(cur_js)

    items = build_items(old_ids, cur_ids)
    endpoints = build_endpoints(old_routes, cur_routes, old_feeds, cur_feeds)
    capabilities = build_capabilities(cur_ids, cur_routes)

    dropped_ids = [i for i in sorted(old_ids) if i not in cur_ids]
    disp_counts: dict[str, int] = {}
    for rec in items:
        disp_counts[str(rec["disposition"])] = disp_counts.get(str(rec["disposition"]), 0) + 1
    endpoint_disp: dict[str, int] = {}
    for rec in endpoints:
        endpoint_disp[str(rec["disposition"])] = endpoint_disp.get(str(rec["disposition"]), 0) + 1

    # Palette contract: every item/endpoint/capability is placed on a known surface.
    used_surfaces = (
        {str(r["surface"]) for r in items}
        | {str(r["surface"]) for r in endpoints}
        | {str(r["surface"]) for r in capabilities}
    )
    unknown_surfaces = sorted(used_surfaces - set(SURFACES))
    if unknown_surfaces:
        raise SystemExit(
            "PARITY BUILD FAILED — surfaces outside the palette:\n  "
            + "\n  ".join(unknown_surfaces)
        )
    surface_counts: dict[str, int] = {s: 0 for s in SURFACES}
    for rec in items + endpoints:
        surface_counts[str(rec["surface"])] += 1
    # Informational only: a target surface may be net-new (R4d, L-WORKFORCE) or a
    # re-composition with no single old id (R3c, L-FLEET). The binding rule is
    # items -> palette, never palette -> items.
    unused_surfaces = sorted(s for s, n in surface_counts.items() if n == 0)

    inputs = [
        {"role": "old_index", "ref": old_ref, "path": OLD_INDEX, "sha256": sha256_text(old_html)},
        {"role": "old_client_js", "ref": old_ref, "path": f"{OLD_JS_DIR}/*.js",
         "sha256": sha256_text(old_js)},
        {"role": "old_routes", "ref": old_ref, "path": "apps/control_room/routes/*.py",
         "sha256": sha256_text("\n".join(_git_show(old_ref, p) for p in OLD_ROUTE_FILES))},
        {"role": "facelift_index", "ref": "working-tree", "path": str(CUR_INDEX.relative_to(ROOT)),
         "sha256": sha256_text(cur_html)},
        {"role": "facelift_client_js", "ref": "working-tree",
         "path": "apps/control_room/static/*.js", "sha256": sha256_text(cur_js)},
        {"role": "facelift_routes", "ref": "working-tree", "path": "apps/control_room/routes/*.py",
         "sha256": sha256_text("".join(
             p.read_text(encoding="utf-8") for p in sorted(CUR_ROUTE_DIR.glob("*.py"))))},
    ]

    return {
        "schema": "control-room-parity-inventory/v1",
        "phase": "u2_parity_inventory",
        "campaign": "control_room_ux_repair",
        "generated_by": "experiments/research/control_room/build_parity_inventory.py",
        "old_ref": old_ref,
        "disposition_vocabulary": {
            "preserve": "Capability retained, essentially as-is.",
            "re-house": "Capability retained but moved into a named region/action/feed.",
            "replace-with-reason": "Capability deliberately replaced by a different pattern; "
                                   "the reason is recorded.",
        },
        "inputs": inputs,
        "summary": {
            "old_unique_ids": len(old_ids),
            "facelift_unique_ids": len(cur_ids),
            "ids_dropped_by_facelift": len(dropped_ids),
            "old_routes": len(set(old_routes)),
            "facelift_routes": len(cur_routes),
            "routes_dropped_by_facelift": len([r for r in set(old_routes) if r not in cur_routes]),
            "old_consumed_feeds": len(old_feeds),
            "facelift_consumed_feeds": len(cur_feeds),
            "dispositions": disp_counts,
            "endpoint_dispositions": endpoint_disp,
            "capabilities": len(capabilities),
            "surface_counts": surface_counts,
            "surfaces_without_old_item": unused_surfaces,
        },
        "surface_palette": SURFACES,
        # Explicit, machine-consumable statement of what the facelift actually did —
        # the "no silent drops" audit reads this rather than recomputing the diff.
        "facelift": {
            "unique_ids": len(cur_ids),
            "dropped_ids": dropped_ids,
            "consumed_feeds": sorted(cur_feeds),
            "registered_routes": sorted(cur_routes),
        },
        "items": items,
        "endpoints": endpoints,
        "capabilities": capabilities,
    }


def _git_list(ref: str, directory: str, suffix: str) -> list[str]:
    """List committed files under ``directory`` at ``ref`` with ``suffix``."""
    try:
        out = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref, directory],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return []
    return [p for p in out.splitlines() if p.endswith(suffix)]


def main() -> int:
    """CLI entry: rebuild the inventory and print a coverage summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-ref", default=OLD_REF,
                        help="git ref holding the old room (default: main)")
    args = parser.parse_args()

    inventory = build(args.old_ref)
    OUT_PATH.write_text(json.dumps(inventory, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    summary = inventory["summary"]
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"  old ids={summary['old_unique_ids']}  facelift ids={summary['facelift_unique_ids']}  "
          f"dropped={summary['ids_dropped_by_facelift']}")
    print(f"  old routes={summary['old_routes']}  facelift routes={summary['facelift_routes']}  "
          f"dropped={summary['routes_dropped_by_facelift']}")
    print(f"  old feeds={summary['old_consumed_feeds']}  "
          f"facelift feeds={summary['facelift_consumed_feeds']}")
    print(f"  item dispositions={summary['dispositions']}")
    print(f"  endpoint dispositions={summary['endpoint_dispositions']}")
    print(f"  capability surfaces={summary['capabilities']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
