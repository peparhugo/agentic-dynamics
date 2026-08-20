"""Portal-owned live design sessions and ExperimentSpec artifact handling.

This module deliberately keeps conversation transport, draft validation, and
artifact mutations behind the Flask process.  Redis stores ownership metadata
and bounded transcript events; the assigned temporary YAML file is the only
exchange boundary between OpenCode and the executable spec.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from agentic_dynamics.experiment.compile_experiment import experiment_matrix
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, validate_spec
from agentic_dynamics.control.live import (
    EVENT_CHANNEL_PREFIX,
    EVENT_LOG_MAX,
    EVENT_LOG_PREFIX,
    STATUS_CHANNEL,
    STATUS_KEY,
)
from agentic_dynamics.control.step_routing import validate_workflow_routing
from agentic_dynamics.control.supervisor import register_event_mapping

try:  # Package import under pytest; sibling import for ``python admin/server.py``.
    from admin.opencode_client import OpenCodeClient, OpenCodeError
except ModuleNotFoundError:  # pragma: no cover - exercised by the documented CLI launch
    from opencode_client import OpenCodeClient, OpenCodeError


DESIGN_SESSIONS_KEY = "control_room:design_sessions"
MAX_DRAFT_BYTES = 1_000_000
MAX_MATRIX_CELLS = 10_000
MATRIX_PREVIEW_CELLS = 50
SAFE_SPEC_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.ya?ml$")
SAFE_SPEC_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _utc_now() -> str:
    """Return stable UTC metadata without host-local timezone ambiguity."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_session_id(response: dict[str, Any]) -> str:
    """Accept the documented native response projection and reject ambiguity."""
    candidate = response.get("id") or response.get("sessionID")
    if candidate is None and isinstance(response.get("data"), dict):
        candidate = response["data"].get("id") or response["data"].get("sessionID")
    if not isinstance(candidate, str) or not candidate:
        raise OpenCodeError("OpenCode session creation omitted the session ID")
    return candidate


def _event_sequence(event: dict[str, Any]) -> str | None:
    """Find the durable aggregate sequence used for reconnect deduplication."""
    properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
    for source in (event, properties):
        for key in ("sequence", "aggregateSequence", "aggregate_sequence", "_sse_id"):
            value = source.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                return str(value)
    return None


def normalize_native_event(event: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Project known native events into existing transcript shapes.

    Native event names may evolve.  Unknown envelopes are kept intact under
    ``native`` rather than dropped, preserving observability and safe frontend
    rendering through ``textContent``.
    """
    properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
    part = properties.get("part") if isinstance(properties.get("part"), dict) else event.get("part")
    event_type = str(event.get("type", ""))
    if isinstance(part, dict):
        part_type = str(part.get("type", ""))
        aliases = {
            "reasoning": "reasoning",
            "text": "text",
            "tool": "tool_use",
            "tool_use": "tool_use",
            "step-start": "step_start",
            "step_start": "step_start",
            "step-finish": "step_finish",
            "step_finish": "step_finish",
        }
        normalized_type = aliases.get(part_type.replace(".", "_").lower())
        if normalized_type:
            return {"type": normalized_type, "part": part, "sessionID": session_id}

    if event_type in {"reasoning", "text", "tool", "tool_use", "step_start", "step_finish"}:
        return {**event, "sessionID": session_id}
    if event_type.startswith("session.status"):
        return {
            "type": "session_status",
            "status": properties.get("status") or event.get("status") or "observed",
            "sessionID": session_id,
        }
    return {"type": event_type or "native_event", "sessionID": session_id, "native": event}


class DesignSessionManager:
    """Own design session metadata, native controls, drafts, and workflow runs."""

    def __init__(
        self,
        *,
        root: Path,
        redis_factory: Callable[[], Any],
        opencode: OpenCodeClient,
        workdirs: dict[str, Path],
        start_relays: bool = True,
    ) -> None:
        self.root = root.resolve()
        self.redis_factory = redis_factory
        self.opencode = opencode
        self.workdirs = {label: path.resolve() for label, path in workdirs.items()}
        self.start_relays = start_relays
        self.draft_dir = Path(tempfile.gettempdir()) / "dynamic-code-control-room-drafts"
        self._relay_threads: dict[str, threading.Thread] = {}
        self._lock = threading.RLock()

    def approved_workdirs(self) -> list[dict[str, str]]:
        """Expose labels, not arbitrary server filesystem paths, to the browser."""
        return [{"key": key, "label": path.name or key} for key, path in self.workdirs.items()]

    def _load_all(self) -> dict[str, dict[str, Any]]:
        """Read only portal-owned metadata from its dedicated Redis hash."""
        raw = self.redis_factory().hgetall(DESIGN_SESSIONS_KEY)
        sessions: dict[str, dict[str, Any]] = {}
        for portal_id, payload in raw.items():
            try:
                value = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("portal_id") == portal_id:
                sessions[portal_id] = value
        return sessions

    def _load(self, portal_id: str) -> dict[str, Any]:
        """Load one owned session or raise a route-friendly missing error."""
        payload = self.redis_factory().hget(DESIGN_SESSIONS_KEY, portal_id)
        if payload is None:
            raise KeyError(portal_id)
        try:
            session = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("design session metadata is unreadable") from error
        if not isinstance(session, dict) or session.get("portal_id") != portal_id:
            raise RuntimeError("design session ownership metadata is invalid")
        return session

    def _store(self, session: dict[str, Any]) -> None:
        """Persist one complete metadata snapshot to avoid split-field reads."""
        self.redis_factory().hset(
            DESIGN_SESSIONS_KEY,
            session["portal_id"],
            json.dumps(session, separators=(",", ":")),
        )

    def _update_metadata(self, portal_id: str, **values: Any) -> dict[str, Any]:
        """Merge fields into the latest snapshot to avoid stale-object erasure."""
        with self._lock:
            latest = self._load(portal_id)
            latest.update(values)
            self._store(latest)
            return latest

    def _write_spec_atomic(self, destination: Path, content: str, *, overwrite: bool) -> bool:
        """Write in the destination directory, atomically preserving no-replace."""
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if overwrite:
                os.replace(temporary_name, destination)
            else:
                try:
                    # Hard-link creation is atomic and refuses an existing name;
                    # unlinking the private temporary name leaves the new file.
                    os.link(temporary_name, destination)
                except FileExistsError:
                    return False
                os.unlink(temporary_name)
            return True
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)

    @staticmethod
    def _public(session: dict[str, Any]) -> dict[str, Any]:
        """Remove private paths while retaining stable browser identities."""
        return {
            "portal_id": session["portal_id"],
            "stream_id": session["stream_id"],
            "opencode_session_id": session.get("opencode_session_id"),
            "kind": session["kind"],
            "title": session["title"],
            "intent": session["intent"],
            "model": session["model"],
            "workdir": session["workdir_key"],
            "workdir_label": session["workdir_label"],
            "lifecycle_state": session.get("lifecycle_state", "unknown"),
            "draft_state": session.get("draft_state", "no_draft"),
            "draft_name": Path(session["draft_path"]).name,
            "revision": session.get("revision", 0),
            "saved_path": session.get("saved_path"),
            "saved_revision": session.get("saved_revision"),
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        }

    def list_sessions(self) -> dict[str, Any]:
        """Return portal-owned sessions, active first and then newest activity."""
        sessions = list(self._load_all().values())
        sessions.sort(
            key=lambda item: (
                item.get("lifecycle_state") not in {"active", "drafting"},
                str(item.get("updated_at", "")),
            ),
            reverse=False,
        )
        # ISO timestamps sort lexically; reverse each lifecycle group explicitly.
        active = [item for item in sessions if item.get("lifecycle_state") in {"active", "drafting"}]
        inactive = [item for item in sessions if item not in active]
        active.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        inactive.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        ordered = active + inactive
        if self.start_relays:
            for item in ordered:
                if item.get("opencode_session_id") and item.get("lifecycle_state") not in {"unavailable"}:
                    self._ensure_relay(item["portal_id"])
        return {"sessions": [self._public(item) for item in ordered], "workdirs": self.approved_workdirs()}

    def _initial_prompt(self, session: dict[str, Any]) -> str:
        """Give OpenCode one artifact boundary and kind-specific constraints."""
        common = (
            f"You are in a live Control Room design session. Maintain the complete ExperimentSpec YAML only at "
            f"{session['draft_path']}. Use repository context when needed, but do not save a spec under "
            "experiments/specs; the operator owns Save. Keep revising the assigned draft after each instruction. "
            "The draft must be accepted by instrument.experiment_spec.validate_spec."
        )
        if session["kind"] == "workflow":
            requirement = (
                " Design a workflow for the feature goal below. Use workflow.kind: agent_task and put an ordered "
                "phase list in workflow.params.phases. Keep a factorial ExperimentSpec with all required fields."
            )
        else:
            requirement = (
                " Design a factorial experiment for the research question below. Include active factors, "
                "measurement/control rules with evidence classes and valid requires/produces, metrics, comparison, "
                "stopping conditions, and adaptation. Policies may require only measured information."
            )
        return f"{common}{requirement}\n\nOperator intent:\n{session['intent']}"

    def create(self, *, kind: str, intent: str, model: str, workdir_key: str) -> dict[str, Any]:
        """Create, seed, persist, and optionally relay one portal-owned session."""
        if not isinstance(kind, str) or kind not in {"workflow", "experiment"}:
            raise ValueError("kind must be 'workflow' or 'experiment'")
        if not isinstance(intent, str) or not intent.strip():
            raise ValueError("feature goal or research question is required")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model is required")
        if not isinstance(workdir_key, str):
            raise ValueError("workdir is not approved")
        workdir = self.workdirs.get(workdir_key)
        if workdir is None:
            raise ValueError("workdir is not approved")
        if not workdir.is_dir():
            raise ValueError("approved workdir is unavailable")

        self.draft_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        portal_id = f"ds_{uuid.uuid4().hex[:12]}"
        draft_path = self.draft_dir / f"{portal_id}.yaml"
        now = _utc_now()
        session: dict[str, Any] = {
            "portal_id": portal_id,
            "stream_id": portal_id,
            "opencode_session_id": None,
            "kind": kind,
            "title": intent.strip().splitlines()[0][:100],
            "intent": intent.strip(),
            "model": model.strip(),
            "workdir_key": workdir_key,
            "workdir_label": workdir.name or workdir_key,
            "workdir_path": str(workdir),
            "draft_path": str(draft_path),
            "draft_state": "no_draft",
            "revision": 0,
            "draft_digest": None,
            "saved_path": None,
            "saved_revision": None,
            "last_sequence": None,
            "lifecycle_state": "creating",
            "created_at": now,
            "updated_at": now,
        }
        self._store(session)
        try:
            native = self.opencode.create_session(location=str(workdir), model=model.strip())
            session["opencode_session_id"] = _extract_session_id(native)
            self.opencode.send_input(
                session["opencode_session_id"],
                self._initial_prompt(session),
                delivery="queue",
            )
        except OpenCodeError:
            session["lifecycle_state"] = "unavailable"
            session["updated_at"] = _utc_now()
            self._store(session)
            raise

        session["lifecycle_state"] = "drafting"
        session["updated_at"] = _utc_now()
        self._store(session)
        self._publish(
            session,
            {"type": "operator", "text": session["intent"], "delivery": "queue", "sessionID": session["opencode_session_id"]},
        )
        if self.start_relays:
            self._ensure_relay(session["portal_id"])
        return self._public(session)

    def _publish(self, session: dict[str, Any], event: dict[str, Any]) -> None:
        """Publish once into the existing bounded Redis transcript transport."""
        payload = json.dumps(event, separators=(",", ":"), default=str)
        redis_client = self.redis_factory()
        register_event_mapping(redis_client, session["stream_id"], event)
        log_key = f"{EVENT_LOG_PREFIX}{session['stream_id']}"
        redis_client.lpush(log_key, payload)
        redis_client.ltrim(log_key, 0, EVENT_LOG_MAX - 1)
        redis_client.publish(f"{EVENT_CHANNEL_PREFIX}{session['stream_id']}", payload)

    def _ensure_relay(self, portal_id: str) -> None:
        """Start at most one daemon relay per session in this Flask process."""
        with self._lock:
            existing = self._relay_threads.get(portal_id)
            if existing and existing.is_alive():
                return
            thread = threading.Thread(target=self._relay, args=(portal_id,), daemon=True, name=f"design-{portal_id}")
            self._relay_threads[portal_id] = thread
            thread.start()

    def _relay(self, portal_id: str) -> None:
        """Reconnect native SSE with durable sequence tracking and bounded backoff."""
        backoff = 1.0
        while True:
            try:
                relayed = self._relay_once(portal_id)
                if relayed:
                    backoff = 1.0
                else:
                    # A clean but empty disconnect should not create a busy loop.
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 15.0)
            except Exception as error:  # Relay failure must not kill the Flask process.
                try:
                    session = self._load(portal_id)
                    session["lifecycle_state"] = "reconnecting"
                    session["relay_error"] = str(error)[:500]
                    session["updated_at"] = _utc_now()
                    self._store(session)
                    self._publish(session, {"type": "relay_error", "message": str(error), "sessionID": session.get("opencode_session_id")})
                except Exception:
                    return
                time.sleep(backoff)
                backoff = min(backoff * 2, 15.0)

    def _relay_once(self, portal_id: str) -> int:
        """Relay one native SSE connection and return the published event count.

        Keeping a single connection pass separate makes durable replay behavior
        deterministic under tests while the daemon wrapper owns reconnect delay.
        """
        session = self._load(portal_id)
        native_id = session.get("opencode_session_id")
        if not native_id:
            return 0
        relayed = 0
        for event in self.opencode.iter_events(native_id, after=session.get("last_sequence")):
            sequence = _event_sequence(event)
            # Aggregate sequences are unique.  Do not republish the event that
            # ended the previous connection if the server replays it.
            if sequence and sequence == session.get("last_sequence"):
                continue
            self._publish(session, normalize_native_event(event, native_id))
            if sequence:
                session["last_sequence"] = sequence
            session = self._update_metadata(
                portal_id,
                last_sequence=session.get("last_sequence"),
                lifecycle_state="active",
                updated_at=_utc_now(),
            )
            relayed += 1
        return relayed

    def send_input(self, portal_id: str, *, prompt: str, delivery: str) -> dict[str, Any]:
        """Admit a bounded operator turn using native queue or steer semantics."""
        if not isinstance(delivery, str) or delivery not in {"queue", "steer"}:
            raise ValueError("delivery must be 'queue' or 'steer'")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt is required")
        session = self._load(portal_id)
        admitted = self.opencode.send_input(session["opencode_session_id"], prompt.strip(), delivery=delivery)
        session = self._update_metadata(portal_id, updated_at=_utc_now(), lifecycle_state="active")
        self._publish(
            session,
            {"type": "operator", "text": prompt.strip(), "delivery": delivery, "admitted": True, "sessionID": session["opencode_session_id"]},
        )
        return {"ok": True, "admitted": True, "delivery": delivery, "response": admitted}

    def interrupt(self, portal_id: str) -> dict[str, Any]:
        """Interrupt only a portal-owned native session, leaving SSE attached."""
        session = self._load(portal_id)
        response = self.opencode.interrupt(session["opencode_session_id"])
        self._update_metadata(portal_id, lifecycle_state="interrupted", updated_at=_utc_now())
        return {"ok": True, "accepted": True, "response": response}

    def draft_state(self, portal_id: str) -> dict[str, Any]:
        """Read one coherent draft snapshot and apply authoritative validation."""
        session = self._load(portal_id)
        path = Path(session["draft_path"])
        validated_at = _utc_now()
        base: dict[str, Any] = {
            "session_id": portal_id,
            "revision": session.get("revision", 0),
            "draft_state": "no_draft",
            "yaml": "",
            "validation": {"valid": False, "errors": [], "validated_at": validated_at},
            "matrix": None,
            "saved": None,
            "capabilities": {"save": False, "run": False, "enqueue": False, "reason": None},
        }
        try:
            file_stat = path.lstat()
        except FileNotFoundError:
            base["capabilities"]["reason"] = "Waiting for the agent to write the assigned draft"
            return base
        except OSError as error:
            base["draft_state"] = "unavailable"
            base["validation"]["errors"] = [f"Draft could not be inspected: {error}"]
            base["capabilities"]["reason"] = "Draft state unavailable"
            return base
        if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
            base["draft_state"] = "unavailable"
            base["validation"]["errors"] = ["Assigned draft must be a regular file, not a symlink"]
            base["capabilities"]["reason"] = "Draft state unavailable"
            return base
        if file_stat.st_size > MAX_DRAFT_BYTES:
            base["draft_state"] = "invalid_yaml"
            base["validation"]["errors"] = [f"Draft exceeds the {MAX_DRAFT_BYTES}-byte limit"]
            return base
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags), "rb") as handle:
                raw = handle.read(MAX_DRAFT_BYTES + 1)
        except OSError as error:
            base["draft_state"] = "unavailable"
            base["validation"]["errors"] = [f"Draft could not be read: {error}"]
            base["capabilities"]["reason"] = "Draft state unavailable"
            return base
        if len(raw) > MAX_DRAFT_BYTES:
            base["draft_state"] = "invalid_yaml"
            base["validation"]["errors"] = [f"Draft exceeds the {MAX_DRAFT_BYTES}-byte limit"]
            return base
        text = raw.decode("utf-8", errors="replace")
        digest = hashlib.sha256(raw).hexdigest()
        with self._lock:
            # Polling requests can overlap.  Compare against the latest digest
            # while assigning the monotonic revision.
            session = self._load(portal_id)
            if digest != session.get("draft_digest"):
                session["revision"] = int(session.get("revision", 0)) + 1
                session["draft_digest"] = digest
                session["updated_at"] = validated_at
        base["revision"] = session["revision"]
        base["yaml"] = text

        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as error:
            base["draft_state"] = "invalid_yaml"
            base["validation"]["errors"] = [str(error)]
            self._update_draft_metadata(session, base)
            return base
        try:
            if not isinstance(document, dict):
                raise ValueError("ExperimentSpec YAML root must be a mapping")
            spec = ExperimentSpec.from_dict(document)
        except (TypeError, ValueError, KeyError) as error:
            base["draft_state"] = "construction_error"
            base["validation"]["errors"] = [str(error)]
            self._update_draft_metadata(session, base)
            return base

        errors = validate_spec(spec)
        # Surface per-step routing validation at Save time (docs/routing_next_steps.md item 2):
        # an unknown ``allowed_models`` id, a duplicate ``model_pool``, or a forbidden/unknown
        # preference signal must fail the draft here, not at run time. The session's default
        # model seeds ``resolve_pool``; routing-inactive specs short-circuit to an empty list.
        errors += validate_workflow_routing(spec, default_model=session.get("model", ""))
        # Session kind is an artifact constraint, not a replacement for the
        # ExperimentSpec validator.  It is evaluated only after validate_spec.
        if not SAFE_SPEC_ID.fullmatch(str(spec.name)):
            errors = [*errors, "spec.name must contain only letters, numbers, underscores, or hyphens"]
        if session["kind"] == "workflow" and spec.workflow.kind != "agent_task":
            errors = [*errors, "workflow design requires workflow.kind 'agent_task'"]
        if session["kind"] == "workflow":
            phases = spec.workflow.params.get("phases") if isinstance(spec.workflow.params, dict) else None
            if not isinstance(phases, list) or not phases or not all(
                isinstance(phase, dict) and phase.get("name") and phase.get("kind") for phase in phases
            ):
                errors = [*errors, "workflow design requires a non-empty workflow.params.phases list"]
        if session["kind"] == "experiment":
            if not spec.rules:
                errors = [*errors, "experiment design requires at least one rule"]
            if not spec.metrics:
                errors = [*errors, "experiment design requires at least one metric"]
            if spec.comparison is None:
                errors = [*errors, "experiment design requires a comparison"]
        base["validation"]["errors"] = errors
        if errors:
            base["draft_state"] = "validation_errors"
            self._update_draft_metadata(session, base)
            return base

        base["draft_state"] = "valid"
        base["validation"]["valid"] = True
        base["capabilities"]["save"] = True
        if session["kind"] == "experiment":
            active_levels = [len(factor.levels) for factor in spec.factors if factor.active]
            cardinality = math.prod(active_levels) if active_levels else 1
            if cardinality > MAX_MATRIX_CELLS:
                base["matrix"] = {"count": cardinality, "preview": [], "truncated": True}
                base["capabilities"]["reason"] = (
                    f"Matrix has {cardinality} cells, above the {MAX_MATRIX_CELLS}-cell preview cap"
                )
            else:
                try:
                    cells = experiment_matrix(spec)
                except Exception as error:
                    base["capabilities"]["reason"] = f"Matrix preview failed: {error}"
                    cells = None
            if cardinality <= MAX_MATRIX_CELLS and cells is not None:
                cell_ids = [cell.get("cell_id") for cell in cells]
                reason = None
                if not cells:
                    reason = "Valid spec produced zero cells"
                elif len(set(cell_ids)) != len(cell_ids):
                    reason = "Valid spec produced duplicate cell IDs"
                elif len(cells) > MAX_MATRIX_CELLS:
                    reason = f"Matrix has {len(cells)} cells, above the {MAX_MATRIX_CELLS}-cell preview cap"
                base["matrix"] = {
                    "count": len(cells),
                    "preview": cells[:MATRIX_PREVIEW_CELLS],
                    "truncated": len(cells) > MATRIX_PREVIEW_CELLS,
                }
                base["capabilities"]["reason"] = reason or "Validated; enqueue unavailable (no generic dispatcher)"

        if session.get("saved_revision") == session["revision"] and session.get("saved_path"):
            base["saved"] = {"revision": session["saved_revision"], "path": session["saved_path"]}
            if session["kind"] == "workflow":
                base["capabilities"]["run"] = True
        self._update_draft_metadata(session, base)
        return base

    def _update_draft_metadata(self, session: dict[str, Any], state: dict[str, Any]) -> None:
        """Persist revision and state after every syntactically bounded read."""
        self._update_metadata(
            session["portal_id"],
            draft_state=state["draft_state"],
            draft_digest=session.get("draft_digest"),
            revision=session.get("revision", 0),
            updated_at=_utc_now(),
        )

    def save(self, portal_id: str, *, filename: str, overwrite: bool) -> dict[str, Any]:
        """Revalidate and atomically persist a safe repository-relative spec."""
        if not SAFE_SPEC_NAME.fullmatch(filename) or Path(filename).name != filename:
            raise ValueError("filename must be a safe .yaml or .yml basename")
        state = self.draft_state(portal_id)
        if not state["validation"]["valid"]:
            raise ValueError("draft is not valid")
        # ``draft_state`` validated this exact coherent snapshot.  Using the
        # returned text prevents an agent write between validation and save.
        content = state["yaml"]
        destination_dir = (self.root / "experiments" / "specs").resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / filename
        if destination.is_symlink():
            raise ValueError("destination symlinks are not allowed")
        if destination.parent.resolve() != destination_dir:
            raise ValueError("destination escapes experiments/specs")
        if destination.exists() and not overwrite:
            return {
                "ok": False,
                "conflict": True,
                "path": destination.relative_to(self.root).as_posix(),
                "message": "Spec already exists; explicit overwrite confirmation is required",
            }

        if not self._write_spec_atomic(destination, content, overwrite=overwrite):
            return {
                "ok": False,
                "conflict": True,
                "path": destination.relative_to(self.root).as_posix(),
                "message": "Spec already exists; explicit overwrite confirmation is required",
            }

        relative = destination.relative_to(self.root).as_posix()
        self._update_metadata(
            portal_id,
            saved_path=relative,
            saved_revision=state["revision"],
            saved_digest=hashlib.sha256(content.encode()).hexdigest(),
            updated_at=_utc_now(),
        )
        return {"ok": True, "path": relative, "revision": state["revision"], "content": content}

    def run_workflow(
        self,
        portal_id: str,
        *,
        goal: str,
        model: str,
        workdir_key: str,
        timeout: int,
        commit: bool,
        backend: str | None = None,
        thinking_budget_tokens: int = 0,
        output_token_limit: int = 0,
    ) -> dict[str, Any]:
        """Launch the existing workflow CLI under a separate fleet identity."""
        session = self._load(portal_id)
        if session["kind"] != "workflow":
            raise ValueError("only workflow design sessions can run")
        state = self.draft_state(portal_id)
        if not state["capabilities"]["run"] or not state.get("saved"):
            raise ValueError("workflow must be valid and saved at the current revision")
        saved_candidate = self.root / state["saved"]["path"]
        if saved_candidate.is_symlink():
            raise ValueError("saved workflow artifact is unavailable or unsafe")
        saved_path = saved_candidate.resolve()
        specs_root = (self.root / "experiments" / "specs").resolve()
        if saved_path.parent != specs_root or not saved_path.is_file():
            raise ValueError("saved workflow artifact is unavailable or unsafe")
        saved_bytes = saved_path.read_bytes()
        if hashlib.sha256(saved_bytes).hexdigest() != session.get("saved_digest"):
            raise ValueError("saved workflow changed after Save; save the current revision again")
        try:
            saved_document = yaml.safe_load(saved_bytes)
            if not isinstance(saved_document, dict):
                raise ValueError("saved ExperimentSpec YAML root must be a mapping")
            saved_spec = ExperimentSpec.from_dict(saved_document)
        except (yaml.YAMLError, TypeError, ValueError, KeyError) as error:
            raise ValueError(f"saved workflow is invalid: {error}") from error
        saved_errors = validate_spec(saved_spec)
        if saved_errors or saved_spec.workflow.kind != "agent_task":
            detail = saved_errors or ["workflow.kind must be 'agent_task'"]
            raise ValueError(f"saved workflow failed validation: {detail}")
        if not goal.strip() or not model.strip():
            raise ValueError("goal and model are required")
        workdir = self.workdirs.get(workdir_key)
        if workdir is None:
            raise ValueError("workdir is not approved")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 7200:
            raise ValueError("timeout must be between 1 and 7200 seconds")
        if backend not in {None, "", "opencode", "claude_cli"}:
            raise ValueError("backend must be opencode or claude_cli")
        budgets = {
            "thinking_budget_tokens": thinking_budget_tokens,
            "output_token_limit": output_token_limit,
        }
        for name, value in budgets.items():
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 2_000_000:
                raise ValueError(f"{name} must be an integer between 0 and 2000000")

        execution_id = f"workflow_{uuid.uuid4().hex[:12]}"
        command = [
            sys.executable,
            "scripts/run_workflow.py",
            "--spec",
            state["saved"]["path"],
            "--goal",
            goal.strip(),
            "--model",
            model.strip(),
            "--workdir",
            str(workdir),
            "--timeout",
            str(timeout),
            "--thinking-budget-tokens",
            str(thinking_budget_tokens),
            "--output-token-limit",
            str(output_token_limit),
        ]
        if backend:
            command.extend(["--backend", backend])
        if not commit:
            command.append("--no-commit")

        redis_client = self.redis_factory()
        redis_client.hset(STATUS_KEY, execution_id, "queued")
        redis_client.publish(STATUS_CHANNEL, json.dumps({"cell_id": execution_id, "status": "queued"}))
        thread = threading.Thread(
            target=self._run_process,
            args=(execution_id, command),
            daemon=True,
            name=execution_id,
        )
        thread.start()
        return {
            "ok": True,
            "execution_id": execution_id,
            "stream_id": execution_id,
            "launch": {
                "spec": state["saved"]["path"],
                "goal": goal.strip(),
                "model": model.strip(),
                "workdir": workdir_key,
                "timeout": timeout,
                "backend": backend or "auto",
                "thinking_budget_tokens": thinking_budget_tokens,
                "output_token_limit": output_token_limit,
                "commit": commit,
            },
        }

    def _run_process(self, execution_id: str, command: list[str]) -> None:
        """Stream workflow CLI output and status through existing fleet channels."""
        redis_client = self.redis_factory()

        def status(value: str) -> None:
            redis_client.hset(STATUS_KEY, execution_id, value)
            redis_client.publish(STATUS_CHANNEL, json.dumps({"cell_id": execution_id, "status": value}))

        status("running")
        environment = os.environ.copy()
        environment["FINOPS_CELL_ID"] = execution_id
        try:
            process = subprocess.Popen(
                command,
                cwd=self.root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            pseudo_session = {"stream_id": execution_id}
            captured: list[str] = []
            captured_bytes = 0
            for line in process.stdout:
                self._publish(pseudo_session, {"type": "text", "part": {"text": line.rstrip()}})
                if captured_bytes < 2_000_000:
                    captured.append(line)
                    captured_bytes += len(line.encode(errors="replace"))
            return_code = process.wait()
            result_ok = False
            if return_code == 0:
                try:
                    document, _end = json.JSONDecoder().raw_decode("".join(captured).lstrip())
                    result_ok = isinstance(document, dict) and document.get("ok") is True
                except (TypeError, json.JSONDecodeError):
                    result_ok = False
            status("done" if result_ok else "failed")
        except Exception as error:
            self._publish({"stream_id": execution_id}, {"type": "run_error", "message": str(error)})
            status("failed")
