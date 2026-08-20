"""The telemetry *contract* — the observe-only publisher seam (refactor-repair Debt-2).

``runtime`` publishes status/phase/event telemetry through this protocol so the Control Room
can show a run as a live cell. The concrete publisher (``control.live.LivePublisher``) is the
control-plane implementation, injected at the composition root (``scripts/run_workflow.py``);
``runtime`` depends on this protocol, never on ``control.live``.
"""

from __future__ import annotations

from typing import Any, Protocol


class TelemetryPublisher(Protocol):
    """The observe-only telemetry seam a workflow run publishes through.

    Matched structurally by ``control.live.LivePublisher`` (which also has an ``enabled`` flag:
    when disabled, the run still completes — telemetry is never a gate).
    """

    enabled: bool

    def set_status(self, status: str) -> None:
        """Mark the cell's overall status (``running``/``done``/``failed``/…)."""

    def set_phase(self, phase: dict[str, Any]) -> None:
        """Mark the current phase (display-only badge data)."""

    def publish_event(self, event: dict[str, Any]) -> None:
        """Append a structured event to the cell's event log."""
