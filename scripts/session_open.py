"""session_open.py — the session OPEN command + the native binding/capsule modes (Unit C).

The s1c deliverable of the ``self_knowledge_layer`` wave (design
``docs/designs/proposed/self_knowledge_layer.md``): opens a session by retrieving the LAST
session's close record and rendering it as the session's opening context — decisions (merged),
open threads, parked items, and the AIO's self-notes on what it got wrong. It is the read half
of the session spine: every session the AIO ends is closed (s1b ``session close``), so the next
session opens with its predecessor's posterior instead of a fresh prior. No prior close
renders a clear first-session bootstrap message.

Four modes share this shell (the first is the historical one; the rest are Unit C's native
binding, the mechanism the AIO capsule plugin calls):

    agentic-dynamics session open [--slug S] [--json]           # the last (or named) close
    session_open.py --binding --native-session-id ID [--json]    # READ the session's binding
    session_open.py --bind --native-session-id ID --agent A --request-file - [...]
                                                                 # CREATE-or-read the binding
    session_open.py --capsule --native-session-id ID [--json]    # COMPOSE the capsule

The binding modes are the durable half of the native session binding: the binding is written
once (first substantive message) and read by every later request — including after a
coordinator restart and after compaction. ``--bind`` never overwrites an existing binding (the
original request is immutable); ``--binding`` distinguishes a MISSING store (unavailable) from
a missing binding (bootstrap); ``--capsule`` composes the bounded capsule from the binding +
the explicitly selected predecessor/records + the control packet + the measured session
budget. Knowledge must not import control: the composition lives HERE (scripts may import
control), and this shell never mutates control state — the packet is read-only.

Identity resolution (the path trap): ``--artifact-dir`` (or ``FINOPS_KB_ARTIFACT_DIR``)
names the durable knowledge root explicitly — a feature worktree's empty
``experiments/results`` is NOT a first-session bootstrap; it is a store-missing state. The
default remains the repo's canonical ``KB_ARTIFACT_DIR``.

Exit codes: 0 on every completed read/compose — bootstrap, store-missing, and capsule-unbound
are machine-readable statuses, never usage errors. 2 on a usage error (missing required
arguments for a mode).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.knowledge import session_ingestion as si  # noqa: E402

#: The script directory — sibling scripts (control_status/session_budget) are invoked from here
#: so the mode works from any cwd.
SCRIPTS_DIR = Path(__file__).resolve().parent

#: The capsule report schema.
CAPSULE_SCHEMA = "session-capsule/v1"

#: The binding report schema.
BINDING_SCHEMA = "session-binding/v1"

#: Default capsule bounds (overridable via ``--max-chars`` / ``--max-records`` / ``--timeout``).
DEFAULT_MAX_CAPSULE_CHARS = 8000
DEFAULT_MAX_RECORDS = 6
DEFAULT_COMMAND_TIMEOUT_S = 20
RECORD_EXCERPT_CHARS = 1000
REQUEST_EXCERPT_CHARS = 2000
CLOSE_LIST_ITEMS = 3
SELF_NOTES_CHARS = 500
CLOSE_ITEM_CHARS = 400
PACKET_APPROVALS = 5
PACKET_SAFE_ACTIONS = 8
#: Each PROTECTED tail field gets its own bound so the tail can never outgrow the capsule
#: bound and lose the fields below it (reviewer reproduction: an oversized next action pushed
#: the blocker out while the text still claimed it was preserved).
TAIL_FIELD_CHARS = 300
#: The floor for the capsule bound: below this the protected tail cannot fit, and a slice
#: applied against the raw request would cut the blocker while claiming preservation. The
#: composer budgets against the floor and records the requested value separately; the plugin
#: mirrors the same floor for its defensive slice.
MIN_CAPSULE_CHARS = 600


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(text: str, limit: int) -> tuple[str, int]:
    """Cut ``text`` to ``limit`` chars, returning ``(text, omitted_chars)``.

    The omitted count is explicit so every bound application can carry a marker — no quiet
    omission, especially never of a controlling constraint (acceptance text, original request).
    """
    text = str(text or "")
    if len(text) <= limit:
        return text, 0
    return text[:limit], len(text) - limit


def _truncate_middle(text: str, limit: int) -> tuple[str, int]:
    """Cut the MIDDLE of ``text``, keeping both ends — controlling constraints live at the ends.

    The reviewer reproduction (2026-09-15): a long acceptance criterion ending in
    ``NEVER DEPLOY`` was rendered head-only, so the constraint vanished without a marker. A
    middle cut keeps the closing constraint; the inline marker names the omitted count.
    """
    text = str(text or "")
    if len(text) <= limit:
        return text, 0
    keep_head = max(1, int(limit * 0.6))
    keep_tail = max(1, limit - keep_head)
    omitted = len(text) - keep_head - keep_tail
    return (
        text[:keep_head] + f"\n[... {omitted} chars omitted ...]\n" + text[-keep_tail:],
        omitted,
    )


def _resolve_artifact_dir(args: argparse.Namespace) -> Path:
    """The durable knowledge root: explicit flag/env first, else the canonical checkout path."""
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    explicit = str(getattr(args, "artifact_dir", "") or os.environ.get("FINOPS_KB_ARTIFACT_DIR", ""))
    return Path(explicit).expanduser() if explicit else KB_ARTIFACT_DIR


# ── external reads (bounded, injectable for tests) ─────────────────────────────


def _run_json_command(cmd: list[str], timeout: float) -> dict:
    """Run a read-only companion script and parse its JSON stdout.

    Never raises. A nonzero exit is NOT automatically a failure: ``session_budget.py`` exits
    1/2 while still emitting a legitimate machine verdict (WARN/UNJUDGED/CLOSE) — so stdout is
    parsed whenever it is a JSON object, and the exit code rides along. Only a timeout, an OS
    error, or unparseable output produces the explicit ``unavailable`` envelope.
    """
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}
    payload = None
    if (proc.stdout or "").strip():
        try:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, dict):
                payload = parsed
        except ValueError:
            payload = None
    if payload is None:
        return {
            "status": "unavailable",
            "reason": f"{Path(cmd[1]).name} exited {proc.returncode}: "
                      f"{(proc.stderr or '').strip()[:300] or 'no parsable JSON'}"
        }
    return {"status": "observed", "payload": payload, "exit_code": proc.returncode}


def read_control_packet(*, timeout: float = DEFAULT_COMMAND_TIMEOUT_S) -> dict:
    """Read the ONE control packet (read-only) for the capsule's packet section."""
    result = _run_json_command(
        [sys.executable, str(SCRIPTS_DIR / "control_status.py"), "--json"], timeout
    )
    if result["status"] != "observed":
        return result
    payload = result["payload"]
    # A real packet carries the full control-status/v1 body (control_epoch included). The
    # CLI's exit-3 error envelope REUSES the schema id, so a schema-only check would render
    # "no database" as an observed empty packet (epoch None, active 0) — the exact conflation
    # the contract forbids. An envelope with ``error`` (or without ``control_epoch``) is not a
    # packet; it is the explicit no-control-database/unavailable state.
    if (
        payload.get("schema") == "control-status/v1"
        and "error" not in payload
        and "control_epoch" in payload
    ):
        return result
    return {
        "status": "no_control_database" if "control database" in json.dumps(payload) else "unavailable",
        "reason": str(payload.get("detail") or payload.get("error") or "not a control-status/v1 packet")[:300],
    }


def measure_budget(native_session_id: str, *, timeout: float = DEFAULT_COMMAND_TIMEOUT_S) -> dict:
    """Measure ``session_budget.py --session-id`` with the NATIVE identity.

    An absent identity or unreadable DB stays UNJUDGED (the script's own contract) — the
    capsule carries the verdict and its reason, never an invented OK.
    """
    result = _run_json_command(
        [
            sys.executable,
            str(SCRIPTS_DIR / "session_budget.py"),
            "--session-id",
            native_session_id,
            "--json",
            "--no-journal",
        ],
        timeout,
    )
    if result["status"] != "observed":
        return {"verdict": "UNJUDGED", "reason": result.get("reason", "measurement unavailable")}
    payload = result["payload"]
    # v2: the resolved model + capacity + provenance ride through so the capsule reports
    # what the judgment was made AGAINST (effective limit, headroom) and where it came from.
    return {
        "verdict": str(payload.get("verdict") or "UNJUDGED"),
        "turns": payload.get("turns"),
        "context_tokens": payload.get("context_tokens"),
        "usage_incomplete": bool(payload.get("usage_incomplete")),
        "post_compaction": bool(payload.get("post_compaction")),
        "reason": str(payload.get("reason") or ""),
        "session_id": str(payload.get("session_id") or ""),
        "model": payload.get("model"),
        "capacity": payload.get("capacity"),
        "remaining_tokens": payload.get("remaining_tokens"),
        "provenance": payload.get("provenance"),
    }


# ── capsule composition (knowledge + control composed HERE) ────────────────────


def _read_record_excerpt(artifact_dir: Path, knowledge_id: str) -> dict:
    """Read ONE referenced record's artifact → a bounded excerpt + its provenance fields."""
    artifact = artifact_dir / f"{knowledge_id}.json"
    entry: dict = {"knowledge_id": knowledge_id, "status": "found"}
    if not artifact.is_file():
        entry["status"] = "unavailable"
        entry["warning"] = f"artifact {knowledge_id}.json is absent under {artifact_dir}"
        return entry
    try:
        record = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        entry["status"] = "unavailable"
        entry["warning"] = f"artifact {knowledge_id}.json is unreadable ({exc})"
        return entry
    if not isinstance(record, dict):
        entry["status"] = "unavailable"
        entry["warning"] = "artifact is not a JSON object"
        return entry
    text = str(record.get("text") or "")
    if " || json: " in text:
        text = text.split(" || json: ", 1)[0]
    excerpt, omitted = _truncate(text, RECORD_EXCERPT_CHARS)
    entry.update(
        {
            "source_type": record.get("source_type"),
            "extractor_version": record.get("extractor_version"),
            "authority": record.get("authority"),
            "evidence_class": record.get("evidence_class"),
            "excerpt": excerpt,
            "truncated": omitted > 0,
            "omitted_chars": omitted,
        }
    )
    return entry


def _bounded_items(items: list, limit: int = CLOSE_ITEM_CHARS) -> list[str]:
    """Bound each list item independently, marking every truncated entry (never a quiet cut)."""
    bounded: list[str] = []
    for item in items:
        text, omitted = _truncate(str(item), limit)
        bounded.append(text + (f" [truncated: {omitted} chars omitted]" if omitted else ""))
    return bounded


def resolve_predecessor(
    binding_payload: dict, *, artifact_dir: Path, max_records: int = DEFAULT_MAX_RECORDS
) -> dict:
    """Resolve the binding's EXPLICITLY selected origin: predecessor close + referenced records.

    The predecessor is the slug the binding names — never "the latest close": an unrelated
    newer close is invisible here by construction. Each explicitly selected ``knowledge_id``
    resolves to a bounded excerpt with its source id; ids beyond the record bound are named in
    ``omitted`` (never silently dropped).
    """
    predecessor = binding_payload.get("predecessor") or None
    if not predecessor:
        return {"status": "none", "note": "no predecessor was bound to this task"}

    resolved: dict = {
        "status": "resolved",
        "slug": predecessor.get("slug"),
        "knowledge_ids": list(predecessor.get("knowledge_ids") or []),
    }
    close = si.open_session(slug=str(predecessor.get("slug")), artifact_dir=artifact_dir)
    if close.status != "opened" or close.payload is None:
        resolved["close"] = {
            "status": "not_found",
            "requested_slug": predecessor.get("slug"),
            "note": "the bound predecessor has no close in this store",
        }
    else:
        payload = close.payload
        resolved["close"] = {
            "status": "found",
            "slug": payload.get("slug"),
            "session_date": payload.get("session_date"),
            "knowledge_id": close.knowledge_id,
            "open_threads": _bounded_items(
                list(payload.get("open_threads") or [])[:CLOSE_LIST_ITEMS]
            ),
            "parked": _bounded_items(list(payload.get("parked") or [])[:CLOSE_LIST_ITEMS]),
            "self_notes": _truncate(str(payload.get("self_notes") or ""), SELF_NOTES_CHARS)[0],
        }

    records: list[dict] = []
    omitted: list[str] = []
    for knowledge_id in resolved["knowledge_ids"]:
        if len(records) >= max_records:
            omitted.append(knowledge_id)
            continue
        records.append(_read_record_excerpt(artifact_dir, knowledge_id))
    resolved["records"] = records
    if omitted:
        resolved["omitted"] = omitted
    return resolved


def compose_capsule(
    binding_payload: dict,
    *,
    artifact_dir: Path,
    packet: dict,
    budget: dict,
    observed_at: str | None = None,
    max_chars: int = DEFAULT_MAX_CAPSULE_CHARS,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> dict:
    """Compose the capsule (schema ``session-capsule/v1``) — bounded, explicit, no quiet cuts.

    Sections: (1) native identity + original task + acceptance + work unit; (2) the explicitly
    selected predecessor and records with source ids; (3) the control packet's facts + degraded/
    unknown states; (4) the measured session-budget verdict; (5) one next action + the blocker.
    """
    request, request_omitted = _truncate_middle(
        str(binding_payload.get("original_request") or ""), REQUEST_EXCERPT_CHARS
    )
    accepted = binding_payload.get("acceptance") or None
    if accepted is not None:
        accepted_text, accepted_omitted = _truncate_middle(
            str(accepted.get("text") or ""), REQUEST_EXCERPT_CHARS
        )
        acceptance = {**accepted, "text": accepted_text, "truncated": accepted_omitted > 0,
                      "omitted_chars": accepted_omitted}
    else:
        acceptance = {"status": "not_stated", "note": "the binding carries no acceptance criteria"}

    predecessor = resolve_predecessor(
        binding_payload, artifact_dir=artifact_dir, max_records=max_records
    )

    packet_section: dict
    if packet.get("status") == "observed":
        payload = packet["payload"]
        projection_lag = payload.get("projection_lag") or {}
        unknowns = [name for name, value in projection_lag.items() if value is None]
        packet_section = {
            "status": "observed",
            "observed_at": observed_at or _now_utc(),
            "control_epoch": payload.get("control_epoch"),
            "repo_head_sha": payload.get("repo_head_sha"),
            "active_runs": len(payload.get("active_runs") or []),
            "awaiting_approvals": [
                {"run_id": a.get("run_id"), "spec": a.get("spec_name") or a.get("spec"),
                 "gate_id": a.get("gate_id")}
                for a in (payload.get("awaiting_approvals") or [])[:PACKET_APPROVALS]
            ],
            "safe_actions": (payload.get("safe_actions") or [])[:PACKET_SAFE_ACTIONS],
            "degraded": [d.get("surface") if isinstance(d, dict) else d
                         for d in (payload.get("degraded") or [])],
            "unknowns": {
                "projection_lag_null": unknowns,
                "note": "null/absent values are LOWER BOUNDS or unknown — never read as zero",
            } if unknowns else {},
        }
    else:
        packet_section = {
            "status": packet.get("status", "unavailable"),
            "observed_at": observed_at or _now_utc(),
            "reason": packet.get("reason", ""),
            "note": "the packet is unavailable — do not substitute memory for it",
        }

    next_action = str(binding_payload.get("next_action") or "").strip()
    if next_action:
        next_section = {"text": next_action, "source": "binding"}
    else:
        close = predecessor.get("close") or {}
        threads = close.get("open_threads") if isinstance(close, dict) else None
        if threads:
            next_section = {"text": str(threads[0]), "source": "predecessor-open-thread"}
        else:
            next_section = {
                "text": "",
                "source": "unavailable",
                "note": "no explicit next action on the binding and no predecessor thread",
            }
    blocker = str(binding_payload.get("blocker") or "").strip()
    blocker_section = (
        {"text": blocker, "source": "binding"} if blocker
        else {"text": "", "source": "none-stated", "note": "no blocker stated on the binding"}
    )

    capsule = {
        "schema": CAPSULE_SCHEMA,
        "observed_at": observed_at or _now_utc(),
        "identity": {
            "native_session_id": binding_payload.get("native_session_id"),
            "resolved_agent": binding_payload.get("resolved_agent"),
            "initiating_message_id": binding_payload.get("initiating_message_id"),
            "task_identity": binding_payload.get("task_identity"),
            "task_identity_source": binding_payload.get("task_identity_source"),
            "project": binding_payload.get("project"),
            "source_revision": binding_payload.get("source_revision"),
        },
        "original_request": {
            "text": request,
            "sha256": binding_payload.get("original_request_sha256"),
            "truncated": request_omitted > 0,
            "omitted_chars": request_omitted,
        },
        "acceptance": acceptance,
        "work_unit": str(binding_payload.get("work_unit") or ""),
        "predecessor": predecessor,
        "control_packet": packet_section,
        "session_budget": {
            "verdict": str(budget.get("verdict") or "UNJUDGED"),
            "turns": budget.get("turns"),
            "context_tokens": budget.get("context_tokens"),
            "usage_incomplete": bool(budget.get("usage_incomplete")),
            "post_compaction": bool(budget.get("post_compaction")),
            "reason": str(budget.get("reason") or ""),
            # Capacity-derived judgment (2026-09-15): the capsule carries the resolved model,
            # the effective/hard limits, the response/compaction headroom, the remaining
            # tokens, and the measurement provenance — never only a bare verdict.
            "model": budget.get("model"),
            "capacity": budget.get("capacity"),
            "remaining_tokens": budget.get("remaining_tokens"),
            "provenance": budget.get("provenance"),
        },
        "next_action": next_section,
        "blocker": blocker_section,
        "bounds": {"max_chars": max_chars, "max_records": max_records},
    }
    effective_max = max(int(max_chars), MIN_CAPSULE_CHARS)
    capsule["bounds"]["requested_max_chars"] = int(max_chars)
    capsule["bounds"]["max_chars"] = effective_max
    head, tail = _render_head(capsule), _render_tail(capsule)
    if len(head) + 1 + len(tail) > effective_max:
        reserve = len(tail) + 130  # the tail + the omission marker
        allowed = max(0, effective_max - reserve)
        omitted = max(0, len(head) - allowed)
        head = head[:allowed] + (
            f"\n[capsule head truncated: {omitted} chars omitted — budget/next action/"
            "blocker preserved below]"
        )
        capsule["bounds"]["truncated"] = True
        capsule["bounds"]["omitted_chars"] = omitted
    else:
        capsule["bounds"]["truncated"] = False
        capsule["bounds"]["omitted_chars"] = 0
    capsule["text"] = head + "\n" + tail
    return capsule


def render_capsule(capsule: dict) -> str:
    """Render the capsule as the text the plugin appends to the system prompt."""
    head, tail = _render_head(capsule), _render_tail(capsule)
    return head + "\n" + tail


def _render_tail(capsule: dict) -> str:
    """The controlling tail — budget verdict, next action, blocker.

    Kept OUT of the head-truncation path so a capsule that hits its size bound can never lose
    the budget verdict, the one next action, or the blocker (the reviewer repair: those must
    survive regardless of how long the request/acceptance/records are).
    """
    budget = capsule["session_budget"]
    field_limit = min(TAIL_FIELD_CHARS, max(60, int(capsule["bounds"].get("max_chars") or MIN_CAPSULE_CHARS) // 4))
    next_text, next_omitted = _truncate(str(capsule["next_action"]["text"] or ""), field_limit)
    next_marker = f" [truncated: {next_omitted} chars omitted]" if next_omitted else ""
    blocker_text, blocker_omitted = _truncate(str(capsule["blocker"]["text"] or ""), field_limit)
    blocker_marker = f" [truncated: {blocker_omitted} chars omitted]" if blocker_omitted else ""
    budget_reason = _truncate(str(budget.get("reason") or ""), 240)[0]
    model = budget.get("model") or {}
    capacity = budget.get("capacity") or {}
    model_text = (
        f"{model.get('provider_id')}/{model.get('model_id')}"
        if model.get("provider_id") else "model unresolved"
    )
    if budget.get("post_compaction"):
        capacity_text = (
            f"post-compaction (pre-compaction reading {budget.get('context_tokens')}; "
            f"measurement resumes with the next completed sample)"
        )
    elif capacity.get("effective_limit"):
        capacity_text = (
            f"context {budget.get('context_tokens')}/{capacity.get('effective_limit')} "
            f"(hard {capacity.get('hard_limit')}, "
            f"headroom {capacity.get('response_headroom_tokens')}"
            + (f", policy {capacity.get('policy_limit')}" if capacity.get("policy_limit") else "")
            + (f", remaining {budget.get('remaining_tokens')}" if budget.get("remaining_tokens") is not None else "")
            + ")"
        )
    else:
        capacity_text = f"context {budget.get('context_tokens')} (capacity unresolved)"
    lines = [
        f"session budget: {budget['verdict']} — {model_text} · {capacity_text} · "
        f"turns {budget.get('turns')} (telemetry)"
        + (f" — {budget_reason}" if budget_reason else ""),
        f"next action: {next_text or '—'} ({capsule['next_action']['source']}){next_marker}",
        f"blocker: {blocker_text or '—'} ({capsule['blocker']['source']}){blocker_marker}",
    ]
    return "\n".join(lines)


def _render_head(capsule: dict) -> str:
    """The head sections — identity, request, acceptance, work unit, predecessor, packet.

    Every section keeps its source ids; every truncation keeps its marker (applied by
    :func:`compose_capsule`); an unavailable dependency is rendered as unavailable, never
    silently absent.
    """
    identity = capsule["identity"]
    lines = [
        f"[AIO capsule — observed {capsule['observed_at']}]",
        f"identity: session {identity['native_session_id']} · agent {identity['resolved_agent']} "
        f"· task {identity['task_identity']} ({identity['task_identity_source']}) "
        f"· message {identity['initiating_message_id'] or '—'} "
        f"· revision {identity['source_revision'] or '—'}",
    ]
    request = capsule["original_request"]
    marker = f" [truncated: {request['omitted_chars']} chars omitted]" if request["truncated"] else ""
    lines.append(f"original request (sha256 {str(request['sha256'])[:12]}): \"{request['text']}\"{marker}")
    acceptance = capsule["acceptance"]
    if acceptance.get("status") == "not_stated":
        lines.append("acceptance: not stated")
    else:
        prov = f" [provenance: {acceptance['provenance']}]" if acceptance.get("provenance") else ""
        trust = " [interpretation — subordinate to the raw request]" if acceptance.get("source") == "interpretation" else ""
        # The omission marker is IN THE TEXT the model receives — not only in JSON metadata
        # the plugin discards (reviewer reproduction 2026-09-15).
        cut = (
            f" [acceptance truncated: {acceptance['omitted_chars']} chars omitted]"
            if acceptance.get("truncated") else ""
        )
        lines.append(
            f"acceptance (v{acceptance.get('version')}, {acceptance.get('source')}): "
            f"\"{acceptance.get('text')}\"{cut}{prov}{trust}"
        )
    lines.append(f"work unit: {capsule['work_unit'] or '—'}")

    pred = capsule["predecessor"]
    if pred.get("status") == "none":
        lines.append("predecessor: none bound (explicit origin absent — bootstrap/unavailable)")
    else:
        close = pred.get("close") or {}
        if close.get("status") == "found":
            lines.append(
                f"predecessor: {pred.get('slug')} close {str(close.get('knowledge_id') or '')[:12]} "
                f"({close.get('session_date')})"
            )
            if close.get("open_threads"):
                lines.append(f"  open threads: {'; '.join(str(t) for t in close['open_threads'])}")
            if close.get("parked"):
                lines.append(f"  parked: {'; '.join(str(p) for p in close['parked'])}")
            if close.get("self_notes"):
                lines.append(f"  self-notes: {close['self_notes']}")
        else:
            lines.append(
                f"predecessor: {pred.get('slug')} — close NOT FOUND in this store "
                f"(bootstrap/unavailable, never treated as permission to pick another)"
            )
        for record in pred.get("records") or []:
            if record.get("status") == "found":
                marker = " [truncated]" if record.get("truncated") else ""
                lines.append(
                    f"  record {str(record.get('knowledge_id'))[:12]} "
                    f"({record.get('source_type')} {record.get('extractor_version')} "
                    f"{record.get('authority')}{record.get('evidence_class')}): "
                    f"\"{record.get('excerpt')}\"{marker}"
                )
            else:
                lines.append(
                    f"  record {str(record.get('knowledge_id'))[:12]}: UNAVAILABLE "
                    f"({record.get('warning')})"
                )
        if pred.get("omitted"):
            lines.append(f"  omitted (record bound): {', '.join(str(i) for i in pred['omitted'])}")

    packet = capsule["control_packet"]
    if packet["status"] == "observed":
        lines.append(
            f"control packet ({packet.get('observed_at')}): epoch {packet.get('control_epoch')} · "
            f"active {packet.get('active_runs')} · awaiting {len(packet.get('awaiting_approvals') or [])} "
            f"· degraded {packet.get('degraded') or '—'}"
        )
        for approval in packet.get("awaiting_approvals") or []:
            lines.append(
                f"  awaiting: {approval.get('run_id')} ({approval.get('spec')}) gate {approval.get('gate_id')}"
            )
        if packet.get("safe_actions"):
            lines.append(f"  safe actions: {json.dumps(packet['safe_actions'], ensure_ascii=False)}")
        if packet.get("unknowns"):
            lines.append(
                f"  unknowns: projection lag null for {packet['unknowns'].get('projection_lag_null')}"
            )
    else:
        lines.append(f"control packet: UNAVAILABLE ({packet.get('reason')})")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics session open",
        description="Open a session: retrieve the last session's close record (decisions, "
        "open threads, parked items, self-notes) as this session's opening context. No prior "
        "close renders a clear first-session bootstrap message. --binding/--bind/--capsule are "
        "the native session-binding modes the AIO capsule plugin calls.",
    )
    parser.add_argument(
        "--slug",
        default="",
        help="the session slot to open (default: the LAST session closed — greatest "
        "session_date, deterministic tie-breaks)",
    )
    parser.add_argument(
        "--repository-id",
        default=si.REPOSITORY_ID,
        help=f"repository identity the org-root read filters on (default: {si.REPOSITORY_ID!r})",
    )
    parser.add_argument(
        "--artifact-dir",
        default="",
        help="the durable knowledge root (bindings + artifacts). Default: FINOPS_KB_ARTIFACT_DIR, "
        "else the canonical checkout's KB_ARTIFACT_DIR. A worktree-local empty dir is NOT a "
        "bootstrap — a missing root is reported as store_missing.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--binding", action="store_true", help="READ the session's binding")
    mode.add_argument("--bind", action="store_true", help="CREATE-or-read the session binding")
    mode.add_argument("--capsule", action="store_true", help="COMPOSE the session capsule")
    mode.add_argument(
        "--update-context", action="store_true",
        help="apply an EXPLICIT, VERSIONED task-context update (the original request is "
             "immutable; --expected-version must match the binding's current version)",
    )
    mode.add_argument(
        "--init-store", action="store_true",
        help="EXPLICITLY initialize the binding store at --artifact-dir (the only operation "
             "that creates the durable root; native binds never do)",
    )
    parser.add_argument("--native-session-id", default="", help="native opencode session id")
    parser.add_argument("--agent", default="", help="resolved agent (output.message.agent)")
    parser.add_argument("--message-id", default="", help="initiating native user-message id")
    parser.add_argument("--request", default="", help="the initiating request text")
    parser.add_argument(
        "--request-file",
        default="",
        help="read the initiating request from this file ('-' = stdin); keeps long requests "
        "off argv",
    )
    parser.add_argument("--task", default="", help="stable task identity (explicit)")
    parser.add_argument("--project", default="", help="native project identity")
    parser.add_argument("--source-revision", default="", help="source/config revision")
    parser.add_argument("--predecessor-slug", default="", help="the EXPLICIT predecessor slug")
    parser.add_argument(
        "--knowledge-id",
        action="append",
        default=[],
        help="an explicitly selected knowledge id to carry in the capsule (repeatable)",
    )
    parser.add_argument("--acceptance", default="", help="acceptance criteria text")
    parser.add_argument(
        "--acceptance-source",
        default="raw",
        choices=list(si.BINDING_ACCEPTANCE_SOURCES),
        help="raw = as stated by the operator; interpretation = extracted by a model "
        "(requires --acceptance-provenance and stays subordinate to the raw request)",
    )
    parser.add_argument("--acceptance-provenance", default="", help="who extracted it, from what")
    parser.add_argument("--work-unit", default="", help="current work unit")
    parser.add_argument("--next-action", default="", help="the one next action for the capsule")
    parser.add_argument("--blocker", default="", help="the actual blocker, if any")
    parser.add_argument(
        "--max-chars", type=int, default=DEFAULT_MAX_CAPSULE_CHARS, help="capsule size bound"
    )
    parser.add_argument(
        "--expected-version", type=int, default=0,
        help="the binding's current context_version (required for --update-context)",
    )
    parser.add_argument(
        "--context-version", type=int, default=1, help="the task-context version to record on --bind"
    )
    parser.add_argument(
        "--max-records", type=int, default=DEFAULT_MAX_RECORDS, help="capsule record bound"
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_COMMAND_TIMEOUT_S,
        help="per-command time bound for the packet/budget reads",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable report (session-open/v1, session-binding/v1, or "
        "session-capsule/v1)",
    )
    return parser


def _open_report(result: si.SessionOpenResult) -> dict:
    """The machine report: what the open resolved, plus the record's durable identity."""
    payload = result.payload or {}
    return {
        "schema": "session-open/v1",
        "status": result.status,
        "slug": result.slug,
        "session_date": payload.get("session_date"),
        "waves_run": payload.get("waves_run", []),
        "merged": payload.get("merged", []),
        "parked": payload.get("parked", []),
        "open_threads": payload.get("open_threads", []),
        "self_notes": payload.get("self_notes", ""),
        "actor": "aio",
        "scope": si.aio_acl_scope(),
        "knowledge_id": result.knowledge_id,
        "entity_id": result.entity_id,
        "artifact": str(result.artifact_path) if result.artifact_path else None,
        "requested_slug": result.requested_slug,
        "candidates": result.candidates,
        "warnings": list(result.warnings),
    }


def _binding_report(result: si.BindingResult) -> dict:
    binding = result.binding or {}
    return {
        "schema": BINDING_SCHEMA,
        "status": result.status,
        "native_session_id": binding.get("native_session_id", ""),
        "binding": result.binding,
        "path": str(result.path) if result.path else None,
        "knowledge_id": result.knowledge_id,
        # The AUTHORIZATION identity (round-9): what the exec gate checks — stable across
        # routine progress recording, advanced only by task-definition changes. Callers
        # (the run_workflow tool) mint the aio block from THESE, never from the
        # content-addressed knowledge_id / context_version.
        "authorization_id": si.binding_authorization_id(binding) if binding else "",
        "authorization_version": si.binding_authorization_version(binding) if binding else 0,
        "warnings": list(result.warnings),
    }


def _request_from_args(args: argparse.Namespace) -> str:
    if args.request_file:
        if args.request_file == "-":
            return sys.stdin.read()
        return Path(args.request_file).read_text(encoding="utf-8")
    return args.request


def _binding_from_args(args: argparse.Namespace, artifact_dir: Path) -> dict:
    request = _request_from_args(args)
    task = str(args.task or "").strip() or f"session:{args.native_session_id}"
    predecessor = None
    if str(args.predecessor_slug or "").strip():
        predecessor = {
            "slug": str(args.predecessor_slug).strip(),
            "knowledge_ids": list(args.knowledge_id or []),
        }
    acceptance = None
    if str(args.acceptance or "").strip():
        acceptance = {
            "text": args.acceptance,
            "version": 1,
            "source": args.acceptance_source,
            "provenance": args.acceptance_provenance,
        }
    return {
        "native_session_id": args.native_session_id,
        "resolved_agent": args.agent,
        "initiating_message_id": args.message_id,
        "task_identity": task,
        "task_identity_source": "explicit" if str(args.task or "").strip() else "session-fallback",
        "project": args.project,
        "original_request": request,
        "source_revision": args.source_revision,
        "acceptance": acceptance,
        "predecessor": predecessor,
        "work_unit": args.work_unit,
        "next_action": args.next_action,
        "blocker": args.blocker,
        "context_version": int(args.context_version or 1),
    }


def _context_from_args(args: argparse.Namespace) -> dict:
    """The task-context fields an update may change (never the original request)."""
    context: dict = {
        "project": args.project,
        "source_revision": args.source_revision,
        "work_unit": args.work_unit,
        "next_action": args.next_action,
        "blocker": args.blocker,
    }
    if str(args.predecessor_slug or "").strip() or args.knowledge_id:
        context["predecessor"] = {
            "slug": str(args.predecessor_slug or "").strip(),
            "knowledge_ids": list(args.knowledge_id or []),
        }
    if str(args.acceptance or "").strip():
        context["acceptance"] = {
            "text": args.acceptance,
            "version": 1,
            "source": args.acceptance_source,
            "provenance": args.acceptance_provenance,
        }
    return context


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = _resolve_artifact_dir(args)

    if args.init_store:
        existed = artifact_dir.is_dir()
        si.init_binding_store(artifact_dir)
        report = {
            "schema": "session-binding-store/v1",
            "status": "initialized",
            "root": str(artifact_dir),
            "created": not existed,
        }
        print(json.dumps(report, indent=2) if args.json else f"[session-open] binding store initialized at {artifact_dir} (created={not existed})")
        return 0

    if args.bind or args.binding or args.capsule or args.update_context:
        if not str(args.native_session_id or "").strip():
            print("[session-open] --native-session-id is required for binding modes", file=sys.stderr)
            return 2
        if args.update_context:
            if str(args.request or "").strip() or str(args.request_file or "").strip():
                print(
                    "[session-open] --update-context never changes the original request — "
                    "create a new binding for a new task instead",
                    file=sys.stderr,
                )
                return 2
            if int(args.expected_version or 0) < 1:
                print("[session-open] --update-context requires --expected-version", file=sys.stderr)
                return 2
            try:
                result = si.update_binding_context(
                    args.native_session_id,
                    context=_context_from_args(args),
                    expected_version=int(args.expected_version),
                    repository_id=args.repository_id,
                    artifact_dir=artifact_dir,
                )
            except ValueError as exc:
                print(f"[session-open] context update refused: {exc}", file=sys.stderr)
                return 2
            report = _binding_report(result)
        elif args.bind:
            binding = _binding_from_args(args, artifact_dir)
            try:
                result = si.write_binding(
                    binding, repository_id=args.repository_id, artifact_dir=artifact_dir
                )
            except ValueError as exc:
                print(f"[session-open] binding refused: {exc}", file=sys.stderr)
                return 2
            report = _binding_report(result)
            # The bind report also echoes how to read it back — the durable contract.
            report["read_with"] = f"--binding --native-session-id {args.native_session_id}"
        else:
            result = si.read_binding(
                args.native_session_id, repository_id=args.repository_id, artifact_dir=artifact_dir
            )
            report = _binding_report(result)
            if args.capsule:
                if result.status != si.BINDING_STATUS_FOUND or result.binding is None:
                    report["capsule"] = None
                    report["capsule_status"] = result.status
                else:
                    capsule = compose_capsule(
                        result.binding,
                        artifact_dir=artifact_dir,
                        packet=read_control_packet(timeout=args.timeout),
                        budget=measure_budget(args.native_session_id, timeout=args.timeout),
                        max_chars=args.max_chars,
                        max_records=args.max_records,
                    )
                    report["capsule"] = capsule
                    report["capsule_status"] = "composed"
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        else:
            print(
                f"[session-open] binding {report['status']}: "
                f"{report.get('native_session_id') or args.native_session_id}"
                + (f" ({report['knowledge_id'][:12]})" if report.get("knowledge_id") else "")
            )
            for warning in report.get("warnings") or []:
                print(f"[session-open] warning: {warning}", file=sys.stderr)
            capsule = report.get("capsule")
            if capsule:
                print(capsule["text"])
            elif report.get("capsule_status"):
                print(f"[session-open] no capsule ({report['capsule_status']})")
        return 0

    result = si.open_session(
        slug=args.slug, repository_id=args.repository_id, artifact_dir=artifact_dir
    )
    if args.json:
        print(json.dumps(_open_report(result), indent=2))
    else:
        print(si.render_opening_context(result))
    for warning in result.warnings:
        print(f"[session-open] warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
