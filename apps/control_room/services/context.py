"""The Control Room's explicit application context (review P2 — the service locator).

The composition root (``apps.control_room.server``) used to hand its dependencies to the route
modules implicitly: every route module did ``from apps.control_room import server`` and read
``server._redis`` / ``server._design_sessions`` / ``server._DUCK`` / ``server._DEMO_MODE`` … at
request time. That is the composition root used as a service locator — a circular conceptual
dependency between the routes and the server, with the tests only passing because they
monkeypatch the server module's private names.

This dataclass makes the dependencies explicit. ``server.py`` builds ONE instance (its own
``build_services()``) and passes it into ``routes.register(app, services)``; each route module
stores it and reads ``services.redis()`` / ``services.design_manager()`` /
``services.supervisor`` … instead of reaching into the server module.

**Injected accessors, never a server-module import.** The live dependencies (the Redis factory,
the design-session manager, the OpenCode/claude clients, the supervisor readers, the manifest /
docs-drift paths) are fields holding zero-argument callables that ``server.py`` binds. This
module therefore does NOT import ``apps.control_room.server`` at all — the application context
is a plain dataclass the composition root populates. The composition root's bindings are
*late-binding* (``lambda: _redis()``, not ``_redis``), so a test's
``monkeypatch.setattr(server, "_redis", …)`` still wins on every later call rather than being
snapshotted when the services object was built.

**Behaviour-identical by construction.** Stable configuration (Redis keys, byte caps, advisory
sets) is copied once at construction: it never changes within a process and is never
monkeypatched, so a plain field is honest where a lazy accessor would be ceremony.

This is a *local* change — the five route modules swap one import and one accessor prefix; no
other module changes shape.

**Injected data sources.** Beyond the service modules and the injected accessors, the
context also carries the *authorities* a route consults for a derived population — currently
:attr:`ControlRoomServices.review_stage_source`. A route must never hard-wire which authority
answers "how many reviews are there?": that binding is a composition-root decision, so it lives
here as an explicit, overridable field. Production binds the file-derived
``pipeline_status.review_stage_summary`` (the reviews on disk are the single source of truth the
pipeline actually writes); a test binds whatever authority it wants and can therefore isolate the
route from the filesystem *completely* — no monkeypatching of module globals, no partial
stubbing. The field is deliberately REQUIRED (no dataclass default) so that dropping the
injection is a loud ``TypeError`` at construction rather than a silent fallback to the real
filesystem, which would let a route quietly re-acquire the dependency the injection removed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

#: An authority that answers "what is the review-stage population?".
#:
#: Takes the request's Redis client and returns one pipeline-stage summary dict (the same shape
#: ``pipeline_status.stage_summary`` returns: ``total``/``queued``/``running``/``done``/… ). The
#: client is passed even to sources that ignore it (the production file-derived source does), so
#: every source shares one signature and a Redis-backed authority stays swappable in.
ReviewStageSource = Callable[[Any], dict[str, Any]]


@dataclass
class ControlRoomServices:
    """The Control Room's injected application context."""

    # -- service modules (the business logic extracted in refactor-repair Debt-1) --
    telemetry: ModuleType
    registry: ModuleType
    supervisor: ModuleType
    design_sessions: ModuleType
    mutations: ModuleType
    docs_health: ModuleType

    # -- stable configuration (copied once at build; never monkeypatched) --
    queue_key: str
    batch_queue_key: str  # the deferred lane (rule 6): depth counts BOTH queues
    results_key: str
    analysis_queue_key: str
    analysis_status_key: str
    review_queue_key: str
    review_status_key: str
    heartbeat_seconds: int
    root: Path
    max_design_prompt_chars: int
    design_delivery_modes: tuple[str, ...]
    claude_agent_advisors: frozenset[str]
    claude_agent_advisor_id_pattern: re.Pattern[str]
    max_claude_agent_log_bytes: int
    max_claude_agent_task_chars: int

    # -- injected data sources (the authority a route consults, chosen by the composition root) --

    #: The authority for the review-stage population served by ``GET /api/matrix``.
    #:
    #: REQUIRED on purpose — see the module docstring. Production binds the file-derived
    #: ``review_stage_summary``; tests bind their own source to isolate the route from disk.
    review_stage_source: ReviewStageSource

    # -- injected live accessors (bound by the composition root; late-binding, so a test's
    # -- monkeypatch of the server module's names still wins on every call) --

    #: A fresh Redis client factory (production: ``server._redis``).
    redis: Callable[[], Any]
    #: The process-local ``DesignSessionManager`` (production: ``server._design_sessions``).
    design_manager: Callable[[], Any]
    #: The server-side OpenCode control client (production: ``server._opencode_client``).
    opencode_client: Callable[[], Any]
    #: The one-shot ``claude`` CLI wrapper (production: ``server._claude_agents``).
    claude_agents: Callable[[], Any]
    #: The approved-workdir allowlist, keyed by workdir label.
    claude_agent_workdirs: Callable[[], dict[str, Path]]
    #: Read retained supervisor flags (production: ``server._load_supervisor_flags``).
    load_supervisor_flags: Callable[[int], tuple[Any, int]]
    #: Recheck ownership before a steer/interrupt.
    authorize_supervisor_action: Callable[[str, str], tuple[Any, Any]]
    #: Best-effort actuation emit (monkeypatched in the supervision tests).
    emit_actuation_record: Callable[..., Any]
    #: The manifest path (monkeypatched in the registry tests).
    data_manifest_path: Callable[[], Path]
    #: The docs-drift rail's state directory (the ``/api/docs-health`` tests point it at a tmp
    #: tree; a late-binding callable keeps that override visible after construction).
    docs_drift_results_dir: Callable[[], Path]

    def operations_snapshot(self) -> tuple[Any, int]:
        """The room's operational read model (step 5): the ONE packet + the attention block.

        The collectors are the CLI's own (``control_status.read_repo_head_sha`` /
        ``read_worker_heartbeats``) and their failures ride the packet's ``degraded`` surface:
        an uncollected git sha or an unreadable Redis is NAMED, never a fabricated value. A
        control plane that cannot be opened is named degraded too — the room must render the
        outage, not 500 on it.
        """
        from datetime import datetime, timezone

        from agentic_dynamics.control import control_status as cs
        from agentic_dynamics.control.control_db import ControlDB
        from apps.control_room.services import operations as ops

        repo_head_sha, git_error = cs.read_repo_head_sha()
        degraded: list[dict[str, str]] = []
        if git_error:
            degraded.append({"surface": "repo_head_sha", "reason": git_error})
        heartbeats: Any = None
        heartbeats, redis_error = cs.read_worker_heartbeats()
        if redis_error:
            heartbeats = None
            degraded.append({"surface": "unhealthy_workers", "reason": redis_error})
        try:
            with ControlDB.open_read_only() as db:
                snapshot = ops.operational_snapshot(
                    db,
                    repo_head_sha=repo_head_sha,
                    heartbeats=heartbeats,
                    # The observation instant is selected at the composition boundary and
                    # passed into the pure read model.  This keeps browser captures stable and
                    # ensures every row in one response shares one age basis.
                    now=datetime.now(timezone.utc).isoformat(),
                )
        except Exception as exc:  # noqa: BLE001 — an unreadable control plane is degraded data
            return {
                "schema": ops.SCHEMA,
                "source": {},
                "attention": [],
                "active_runs": [],
                "promotable_runs": [],
                "failed_runs": [],
                "runs": [],
                "state_screens": [],
                "safe_actions": [],
                "unhealthy_workers": [],
                "projection_lag": {},
                "degraded": degraded
                + [{"surface": "control_db", "reason": f"{type(exc).__name__}: {exc}"}],
            }, 200
        snapshot["degraded"] = list(snapshot.get("degraded", [])) + degraded
        return snapshot, 200

    def run_detail(self, run_id: str) -> tuple[Any, int]:
        """The P1/P2 per-run detail; unknown run -> 404, unreadable control plane -> named 200.

        The run's job log rides the same read: the injected Redis accessor is passed INTO the
        pure read model (which owns no connection of its own), and an accessor that cannot
        produce a client leaves a NAMED ``unavailable`` logs block — never a 500, never a
        silently empty log.
        """
        from datetime import datetime, timezone

        from agentic_dynamics.control.control_db import ControlDB
        from apps.control_room.services import operations as ops

        redis_client: Any = None
        redis_error = ""
        try:
            redis_client = self.redis()
        except Exception as exc:  # noqa: BLE001 — a named absence, never a 500
            redis_error = f"{type(exc).__name__}: {exc}"
        try:
            with ControlDB.open_read_only() as db:
                detail = ops.run_detail(
                    db,
                    run_id,
                    redis_client=redis_client,
                    now=datetime.now(timezone.utc).isoformat(),
                )
        except Exception as exc:  # noqa: BLE001 — named degradation, never a 500
            return {
                "error": "control_db_unavailable",
                "reason": f"{type(exc).__name__}: {exc}",
            }, 200
        if detail is None:
            return {"error": "run not found", "run_id": run_id}, 404
        if redis_error:
            detail["logs"] = ops.logs_block(cell_id="", state="unavailable", reason=redis_error)
        return detail, 200

    # -- the analytic projections (step 6, P3/P4/P5/P6; read-only, on-demand) --

    def quality(self) -> tuple[Any, int]:
        """P3 ``model_quality``: Grit / first-pass / narration / coverage.

        The canonical corpus is the input door (never a re-derivation); an unreadable corpus
        is NAMED degraded with empty models — never a fabricated zero population. The
        workflow-ledger half (first-pass) degrades to zero attempt rows.
        """
        from datetime import datetime, timezone

        from agentic_dynamics.control.projections import model_quality as mq
        from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables

        now = datetime.now(timezone.utc).isoformat()
        degraded: list[dict[str, str]] = []
        source: dict[str, Any] = {}
        findings: list[dict[str, Any]] = []
        stories: list[dict[str, Any]] = []
        try:
            tables = load_canonical_tables("finding", "story")
            findings, stories = tables.findings, tables.stories
            source = {
                "input_dataset_id": tables.input_dataset_id,
                "registry_version": tables.identity.registry_version,
            }
        except Exception as exc:  # noqa: BLE001 — named degradation, never a 500
            degraded.append(
                {"surface": "canonical_corpus", "reason": f"{type(exc).__name__}: {exc}"}
            )
        attempts, n_ledgers = mq.load_workflow_attempts(
            self.root / "experiments" / "results" / "workflows"
        )
        source["workflow_ledgers"] = n_ledgers
        payload = mq.build_model_quality(findings, stories, attempts, now=now, source=source)
        payload["degraded"] = list(payload.get("degraded", [])) + degraded
        return payload, 200

    def story_arc(self, name: str) -> tuple[Any, int]:
        """P4 ``story_arc``: the named story's session arc; unknown name -> 404."""
        from datetime import datetime, timezone

        from agentic_dynamics.control.projections import story_arc as sa
        from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables

        now = datetime.now(timezone.utc).isoformat()
        degraded: list[dict[str, str]] = []
        source: dict[str, Any] = {}
        stories: list[dict[str, Any]] = []
        try:
            tables = load_canonical_tables("story")
            stories = tables.stories
            source = {
                "input_dataset_id": tables.input_dataset_id,
                "registry_version": tables.identity.registry_version,
            }
        except Exception as exc:  # noqa: BLE001 — named degradation, never a 500
            degraded.append(
                {"surface": "canonical_corpus", "reason": f"{type(exc).__name__}: {exc}"}
            )
        payload = sa.build_story_arc(stories, name, now=now, source=source)
        if payload is None:
            if degraded:
                return {
                    "schema": sa.SCHEMA,
                    "story": name,
                    "state": "unavailable",
                    "degraded": degraded,
                }, 200
            return {"error": "story not found", "story": name}, 404
        payload["degraded"] = list(payload.get("degraded", [])) + degraded
        return payload, 200

    def run_value(self, *, run: str | None = None, arm: str | None = None) -> tuple[Any, int]:
        """P5 ``run_value``: observed-only accepted outcomes + cost per accepted outcome.

        Rows come from the attempt ledgers; optional ``run``/``arm`` exact-match filters
        narrow the population. No ledger directory is an honest empty population.
        """
        from datetime import datetime, timezone

        from agentic_dynamics.control.projections import run_value as rv

        now = datetime.now(timezone.utc).isoformat()
        rows, paths = rv.load_attempt_value_rows(self.root / "experiments" / "results")
        if run is not None:
            rows = [r for r in rows if r["run"] == run]
        if arm is not None:
            rows = [r for r in rows if r["arm"] == arm]
        payload = rv.build_run_value(rows, now=now, source={"attempt_ledgers": paths})
        return payload, 200

    def arm_comparison(self, spec: str | None = None) -> tuple[Any, int]:
        """P6 ``arm_comparison``: the compare/adapt ranking over real executed phases.

        The shadow-decision calibration is best-effort (a missing decision store yields the
        unmeasured calibration, never an error).
        """
        from datetime import datetime, timezone

        from agentic_dynamics.control.projections import arm_comparison as ac
        from agentic_dynamics.control.rules import load_shadow_decisions

        now = datetime.now(timezone.utc).isoformat()
        rows, n_ledgers = ac.load_phase_outcomes(
            self.root / "experiments" / "results" / "workflows"
        )
        try:
            decisions = load_shadow_decisions()
        except Exception:  # noqa: BLE001 — calibration is best-effort telemetry
            decisions = []
        payload = ac.build_arm_comparison(
            rows,
            spec=spec,
            decisions=decisions,
            now=now,
            source={"workflow_ledgers": n_ledgers},
        )
        return payload, 200

    # -- the step-7 modeled/scenario surfaces (rule 4/6/8/9; measured where owned) --

    def _published_website_data(self) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
        """Read the generated site data best-effort; a failure is a NAMED degradation."""
        from apps.control_room.services.published import load_published_data

        try:
            return load_published_data(self.root / "apps" / "website" / "data.js"), []
        except Exception as exc:  # noqa: BLE001 — scenario surfaces degrade to named unknowns
            return None, [{"surface": "published_data", "reason": f"{type(exc).__name__}: {exc}"}]

    def _queue_jobs(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        """Read BOTH lanes best-effort, tagging each job with its lane and ``batch_mode``.

        The lane IS the mode (rule 6, step 12): on-demand jobs carry ``batch_mode: false``,
        deferred-lane jobs ``true`` — so the split is measured from the queue itself, and a
        job that never carried the marker is still classified by where it waits. A failure is
        a NAMED degradation, never a 500.
        """
        from agentic_dynamics.control.queue_reinterleave import read_queue

        try:
            rows: list[dict[str, Any]] = []
            for lane, key in (("on_demand", "story_jobs"), ("batch", "story_jobs_batch")):
                for job in read_queue(self.redis(), key=key) or []:
                    row = dict(job)
                    row["lane"] = lane
                    row["batch_mode"] = lane == "batch"
                    rows.append(row)
            return rows, []
        except Exception as exc:  # noqa: BLE001 — dashboard telemetry may degrade
            return [], [{"surface": "queue", "reason": f"{type(exc).__name__}: {exc}"}]

    def sla_queue(self, window_h: int = 72) -> tuple[Any, int]:
        """P8: queue depth + measured completions + the 2× depth rule (writer-less fields named)."""
        from datetime import datetime, timezone

        from agentic_dynamics.control.control_db import ControlDB
        from agentic_dynamics.control.projections import sla_queue as sq

        now = datetime.now(timezone.utc).isoformat()
        queue_jobs, degraded = self._queue_jobs()
        attempts: list[dict[str, Any]] = []
        try:
            with ControlDB.open_read_only() as db:
                attempts = [
                    {
                        "job_id": attempt.step_id,
                        "model": attempt.model,
                        "state": attempt.state.value,
                        "started_at": attempt.started_at,
                        "ended_at": attempt.ended_at,
                    }
                    for attempt in db.recent_attempts(limit=200)
                ]
        except Exception as exc:  # noqa: BLE001 — named degradation, never a 500
            degraded.append({"surface": "control_db", "reason": f"{type(exc).__name__}: {exc}"})
        views, n_ledgers = sq.load_breach_views(self.root / "experiments" / "results" / "workflows")
        timings, n_skipped = sq.load_job_timings(
            self.root / "experiments" / "results" / "queue_timings.jsonl"
        )
        payload = sq.build_sla_queue(
            queue_jobs,
            attempts,
            views,
            timings=timings,
            window_h=window_h,
            now=now,
            source={
                "workflow_ledgers": n_ledgers,
                "recent_attempts": len(attempts),
                "timing_rows": len(timings),
                "timing_rows_skipped": n_skipped,
            },
        )
        payload["degraded"] = list(payload.get("degraded", [])) + degraded
        return payload, 200

    def escalation(self, spec: str | None = None) -> tuple[Any, int]:
        """P9: the cascade surface — recorded events only; E_x from the published measurement.

        The human-escalation counter (G-29) reads the recorded human-attributed escalation
        decision records (category ``escalate``, human actor); a decision-artifact anomaly is
        NAMED in ``degraded``, never silently dropped.
        """
        from datetime import datetime, timezone

        from agentic_dynamics.control.projections import escalation as esc

        now = datetime.now(timezone.utc).isoformat()
        rows, n_ledgers = esc.load_escalation_attempts(
            self.root / "experiments" / "results" / "workflows"
        )
        human_events, human_warnings = esc.load_human_escalation_events(
            self.root / "experiments" / "results" / "kb"
        )
        published, degraded = self._published_website_data()
        degraded = list(degraded) + [
            {"surface": "decision_records", "reason": warning} for warning in human_warnings
        ]
        payload = esc.build_escalation_cascade(
            rows,
            spec=spec,
            published=published,
            human_events=human_events,
            now=now,
            source={"workflow_ledgers": n_ledgers, "human_events": len(human_events)},
        )
        payload["degraded"] = list(payload.get("degraded", [])) + degraded
        return payload, 200

    def decisions(self, category: str | None = None) -> tuple[Any, int]:
        """P11 ``decision_ledger``: recorded decisions + P0 acts whose record is MISSING.

        Reads the durable decision artifacts (the same read seam the record command uses) and the
        control DB's approvals/promotions. A decision artifact that cannot be classified is NAMED
        in ``degraded``; an unreachable control plane degrades to the record half with a named
        reason — never a fabricated approvals/promotions population.
        """
        from datetime import datetime, timezone

        from agentic_dynamics.control.control_db import ControlDB
        from agentic_dynamics.control.projections import decision_ledger as dl

        now = datetime.now(timezone.utc).isoformat()
        artifact_dir = self.root / "experiments" / "results" / "kb"
        degraded: list[dict[str, str]] = []
        records: list[Any] = []
        try:
            records, warnings = dl.load_decision_records(artifact_dir=artifact_dir)
        except Exception as exc:  # noqa: BLE001 — named degradation, never a 500
            warnings = [f"{type(exc).__name__}: {exc}"]
        for warning in warnings:
            degraded.append({"surface": "decision_records", "reason": warning})

        source = {"decision_artifact_dir": str(artifact_dir)}
        try:
            with ControlDB.open_read_only() as db:
                payload = dl.build_decision_ledger(
                    db, records, category=category, now=now, source=source
                )
        except Exception as exc:  # noqa: BLE001 — an unreadable control plane is degraded data
            degraded.append({"surface": "control_db", "reason": f"{type(exc).__name__}: {exc}"})
            payload = dl.build_decision_ledger(
                None, records, category=category, now=now, source=source
            )
        payload["degraded"] = list(payload.get("degraded", [])) + degraded
        return payload, 200

    def batch(self) -> tuple[Any, int]:
        """P10: the batch surface — not-measurable until a ``batch_mode`` marker exists."""
        from datetime import datetime, timezone

        from agentic_dynamics.control.projections import batch as batch_projection

        now = datetime.now(timezone.utc).isoformat()
        jobs, degraded = self._queue_jobs()
        payload = batch_projection.build_batch(jobs, now=now, source={"queue_scanned": True})
        payload["degraded"] = list(payload.get("degraded", [])) + degraded
        return payload, 200

    def energy(self) -> tuple[Any, int]:
        """Rule 4: the EPM/energy scenario surface (published sources + the named measured gap)."""
        from datetime import datetime, timezone

        from agentic_dynamics.control.projections import energy as energy_projection

        now = datetime.now(timezone.utc).isoformat()
        published, degraded = self._published_website_data()
        payload = energy_projection.build_energy(published, now=now)
        payload["degraded"] = list(payload.get("degraded", [])) + degraded
        return payload, 200
