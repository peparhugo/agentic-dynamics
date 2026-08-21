"""Manifest-registry routes (table + lineage).

Extracted from ``server.py`` (refactor-repair Debt-1). Pure file reads over the cached compacted
registry; ``_services.data_manifest_path`` is read through ``server.*`` so the tests' monkeypatch
keeps working.
"""
from __future__ import annotations

from typing import Any

from flask import Response, jsonify, request

from apps.control_room.services.context import ControlRoomServices
from apps.control_room.services.registry import _load_registry_cached
from scripts import registry as registry_cli

#: The injected application context, bound by ``register()`` before any request is served.
_services: ControlRoomServices | None = None

def api_registry() -> Response:
    """Filterable table over the manifest's registry array — GET only, read-only by
    construction (same invariant as ``/api/flags`` and ``/api/matrix`` — no
    ``send_input``/``interrupt`` anywhere in this file, unchanged by this design).

    Canonical-state round 2, plan step 17. Reads ``experiments/data_manifest.json``'s
    ``registry`` array (``generate_manifest.py``'s compacted output, plan step 15) —
    never Redis, never Neo4j: this route is a pure file read, matching
    ``scripts/registry.py query``'s zero-external-dependency philosophy exactly (in
    fact it reuses that module's ``load_registry`` directly rather than re-implementing
    manifest loading a second time). Query params mirror the CLI's ``query`` flags:
    ``record_type`` / ``lifecycle`` / ``since`` (the CLI's ``--record-type``/etc, with
    argparse's dash-to-underscore convention already applied since these are query
    string keys, not flags).
    """
    rows = _load_registry_cached(_services.data_manifest_path)

    record_type = request.args.get("record_type")
    if record_type:
        rows = [r for r in rows if r.get("source_type") == record_type]

    lifecycle = request.args.get("lifecycle")
    if lifecycle:
        rows = [r for r in rows if r.get("lifecycle_state") == lifecycle]

    since = request.args.get("since")
    if since:
        rows = [r for r in rows if str(r.get("observed_at") or "") >= since]

    return jsonify({"registry": rows, "count": len(rows)})

def api_registry_lineage(entity_id) -> Response:
    """Lineage view for one entity: its own row plus, for an actuation record, the
    justifying observation resolved through ``causes`` (design §10 / §5a — "why did the
    system decide to act" stays a one-hop lookup even though nothing constructs an
    actuation record today, see ``src/instrument/actuation_ingestion.py``).

    Deliberately file-only, like ``/api/registry`` above — this route never queries
    Neo4j. The compacted registry array keeps only the CURRENT row per ``entity_id``
    (that is the entire point of ``generate_manifest.py``'s compaction step), so a full
    ``SUPERSEDES`` version chain is out of scope for an HTTP route by construction; that
    remains ``scripts/registry.py lineage <entity_id> --live``'s job, not this one's —
    adding a live Neo4j round-trip to an HTTP request handler would be a materially
    heavier dependency than this read-only surface needs for the one-hop view it exists
    to serve.
    """
    rows = _load_registry_cached(_services.data_manifest_path)
    matches = [r for r in rows if r.get("entity_id") == entity_id]
    if not matches:
        return jsonify({"error": "not_found", "entity_id": entity_id}), 404
    if len(matches) > 1:
        # Compaction guarantees one row per entity_id, so this is only reachable
        # with a malformed/duplicate manifest. Mirror registry.py's ``cmd_show``
        # and surface the ambiguity instead of silently returning the first row
        # (review F5).
        return jsonify({
            "error": "ambiguous",
            "entity_id": entity_id,
            "count": len(matches),
            "records": matches,
        }), 409

    record = matches[0]
    response: dict[str, Any] = {"record": record}
    if record.get("source_type") == "actuation" and record.get("causes"):
        _stage, causes_matches = registry_cli.resolve_show(rows, record["causes"])
        response["causes_record"] = causes_matches[0] if causes_matches else None
    return jsonify(response)

def register(app, services: ControlRoomServices) -> None:
    """Register this module's routes on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/registry")(api_registry)
    app.get("/api/registry/<entity_id>")(api_registry_lineage)
