"""Telemetry service — retained-window snapshot, event sampling, and SSE.

Extracted from ``server.py`` (refactor-repair Debt-1). Pure decoding/aggregation plus the SSE
envelope; the per-cell Redis reads are driven by the caller. ``EVENT_LOG_MAX`` /
``RETAINED_SAMPLES_MAX`` are read through ``server.*`` so the matrix tests' monkeypatch of
``server.EVENT_LOG_MAX`` keeps working.
"""
from __future__ import annotations

import json
import math
from typing import Any

from flask import Response

from agentic_dynamics.control.live import EVENT_LOG_PREFIX
from apps.control_room import server


def _sse(generator) -> Response:
    """Return a response configured for an unbuffered SSE connection."""
    return Response(
        generator,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

def _reported_number(value) -> float | None:
    """Return valid reported telemetry as a float, or ``None``.

    Telemetry is observational rather than billing data, so malformed values
    must be ignored instead of coerced. In particular, booleans are excluded
    even though Python treats them as integers.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None

def _event_timestamp(event, part) -> str | int | float | None:
    """Return a supplied event timestamp without inventing server time."""
    for container in (event, part):
        for key in ("timestamp", "time", "created_at", "createdAt"):
            value = container.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                return value
    return None

def _identity_number(value) -> str:
    """Format a telemetry number identically to the browser identity helper."""
    if value is None:
        return ""
    return f"{value:.12f}".rstrip("0").rstrip(".") or "0"

def _step_sample(payload) -> dict[str, Any] | None:
    """Extract one defensive token/cost sample from a raw event payload.

    Both current events (fields under ``part``) and retained legacy events
    (top-level fields) are supported. A step with no valid token or cost value
    is omitted because it cannot contribute to a chart or aggregate.
    """
    try:
        event = json.loads(payload) if isinstance(payload, str) else payload
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(event, dict):
        return None

    event_type = str(event.get("type", "")).replace("-", "_").lower()
    if event_type != "step_finish":
        return None
    part = event.get("part") if isinstance(event.get("part"), dict) else event
    tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}

    input_tokens = _reported_number(tokens.get("input"))
    output_tokens = _reported_number(tokens.get("output"))
    reasoning_tokens = _reported_number(tokens.get("reasoning"))
    total_tokens = _reported_number(tokens.get("total"))
    cache = tokens.get("cache")
    cache_tokens = _reported_number(cache)
    if isinstance(cache, dict):
        cache_values = [_reported_number(cache.get("read")), _reported_number(cache.get("write"))]
        valid_cache = [value for value in cache_values if value is not None]
        cache_tokens = sum(valid_cache) if valid_cache else None

    # Some providers omit ``total``. Summing only explicitly reported fields
    # yields a useful bar without manufacturing missing token values as zero.
    if total_tokens is None:
        components = [input_tokens, output_tokens, reasoning_tokens, cache_tokens]
        reported_components = [value for value in components if value is not None]
        total_tokens = sum(reported_components) if reported_components else None

    cost = _reported_number(part.get("cost"))
    if cost is None and total_tokens is None:
        return None

    timestamp = _event_timestamp(event, part)
    session_id = event.get("sessionID") or part.get("sessionID")
    identity = "|".join([
        str(session_id or ""),
        str(timestamp if timestamp is not None else ""),
        _identity_number(cost),
        _identity_number(input_tokens),
        _identity_number(output_tokens),
        _identity_number(reasoning_tokens),
        _identity_number(cache_tokens),
        _identity_number(total_tokens),
    ])
    return {
        "identity": identity,
        "timestamp": timestamp,
        "cost": cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_tokens": cache_tokens,
        "total_tokens": total_tokens,
    }

def _retained_telemetry(redis_client, cell_ids) -> dict[str, Any]:
    """Build an additive retained-window snapshot from existing event logs.

    Each log is independently optional. A transient per-cell read failure does
    not erase the baseline matrix response; ``available`` records that the
    telemetry extension is incomplete while the legacy status data remains
    usable.

    All log reads are issued in a single non-transactional pipeline so the
    fleet snapshot costs one round trip, not one per cell.
    """
    cells = {}
    total_cost = 0.0
    input_tokens = 0.0
    output_tokens = 0.0
    cost_samples = input_samples = output_samples = 0
    available = True
    capped = False

    keys = [f"{EVENT_LOG_PREFIX}{cell_id}" for cell_id in cell_ids]
    try:
        pipe = redis_client.pipeline(transaction=False)
        for key in keys:
            pipe.lrange(key, 0, -1)
        histories = pipe.execute()
    except Exception:
        # A connection-level failure marks telemetry incomplete but must not
        # erase the legacy matrix response (same contract as today).
        histories = [None] * len(cell_ids)

    for cell_id, history in zip(cell_ids, histories, strict=False):
        if history is None:
            available = False
            history = []
        capped = capped or len(history) >= server.EVENT_LOG_MAX

        samples = []
        for payload in reversed(history):
            sample = _step_sample(payload)
            if sample is None:
                continue
            samples.append(sample)
            if sample["cost"] is not None:
                total_cost += sample["cost"]
                cost_samples += 1
            if sample["input_tokens"] is not None:
                input_tokens += sample["input_tokens"]
                input_samples += 1
            if sample["output_tokens"] is not None:
                output_tokens += sample["output_tokens"]
                output_samples += 1

        cell_costs = [sample["cost"] for sample in samples if sample["cost"] is not None]
        cell_inputs = [
            sample["input_tokens"] for sample in samples if sample["input_tokens"] is not None
        ]
        cell_outputs = [
            sample["output_tokens"] for sample in samples if sample["output_tokens"] is not None
        ]
        cells[cell_id] = {
            "reported_cost": sum(cell_costs) if cell_costs else None,
            "input_tokens": sum(cell_inputs) if cell_inputs else None,
            "output_tokens": sum(cell_outputs) if cell_outputs else None,
            "latest_cost": cell_costs[0] if cell_costs else None,
            "samples": samples[:server.RETAINED_SAMPLES_MAX],
            "history_size": len(history),
            "history_capped": len(history) >= server.EVENT_LOG_MAX,
            "partial": True,
        }

    return {
        "available": available,
        "provenance": "retained_window",
        "partial": True,
        "reported_cost": total_cost if cost_samples else None,
        "input_tokens": input_tokens if input_samples else None,
        "output_tokens": output_tokens if output_samples else None,
        "cost_samples": cost_samples,
        "history_capped": capped,
        "cells": cells,
    }

def _parse_phases(payloads) -> dict[str, dict[str, Any]]:
    """Decode the ``story_phase`` hash into ``{cell_id: {name, index, total}}``.

    Each value is a JSON object written by ``LivePublisher.set_phase``. A malformed
    or empty entry is dropped (the badge is display-only), so a partial write can
    never affect the matrix status contract.
    """
    phases: dict[str, dict[str, Any]] = {}
    for cell_id, raw in payloads.items():
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(parsed, dict) or not parsed.get("name"):
            continue
        phases[cell_id] = {
            "name": parsed.get("name"),
            "index": parsed.get("index"),
            "total": parsed.get("total"),
        }
    return phases
