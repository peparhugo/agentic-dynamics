"""Telemetry service — retained-window snapshot, event sampling, and SSE.

Extracted from ``server.py`` (refactor-repair Debt-1). Pure decoding/aggregation plus the SSE
envelope; the per-cell Redis reads are driven by the caller. ``EVENT_LOG_MAX`` /
``RETAINED_SAMPLES_MAX`` are read through ``server.*`` so the matrix tests' monkeypatch of
``server.EVENT_LOG_MAX`` keeps working.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from flask import Response

from agentic_dynamics.control.live import EVENT_LOG_PREFIX
from apps.control_room import server

#: The live window (seconds) — the watchdog horizon the Control Room's LIVE NOW section
#: keys off. A phase published within this window (or a runner-telemetry tail stamp of that
#: age) marks a run LIVE; past it, the run leaves LIVE NOW and shows its age in history.
#: The window, never the publishing process, decides liveness.
LIVE_WINDOW_SECONDS = 600


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

def _stamp_to_datetime(value):
    """Parse a telemetry stamp into an aware UTC datetime, or ``None``.

    Accepts ISO-8601 strings (``Z`` or ``+00:00``, with or without sub-second
    precision) and numeric epochs. A number >= 1e11 is treated as milliseconds
    (the opencode event timestamps), anything smaller as seconds. A naive ISO
    string is assumed UTC so it can be compared against the server clock.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number) or number < 0:
            return None
        epoch_seconds = number / 1000.0 if number >= 1e11 else number
        try:
            return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    try:
        number = float(text)
    except ValueError:
        return None
    epoch_seconds = number / 1000.0 if number >= 1e11 else number
    try:
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _tail_stamps(redis_client, cell_ids) -> dict[str, Any]:
    """Read the newest retained event per cell and return its timestamp (the runner-telemetry signal).

    One non-transactional pipeline costs a single round trip regardless of fleet size, and
    each log is independently optional: a per-cell read failure degrades that cell to no
    timestamp (age-unknown), never to a 503. The head of the tail is the natural
    last-activity proxy — the raw opencode session events carry a top-level ``timestamp``
    (ms epoch) that ``_event_timestamp`` already knows how to read.
    """
    keys = [f"{EVENT_LOG_PREFIX}{cell_id}" for cell_id in cell_ids]
    try:
        pipe = redis_client.pipeline(transaction=False)
        for key in keys:
            pipe.lrange(key, 0, 7)
        heads = pipe.execute()
    except Exception:
        heads = [None] * len(cell_ids)

    stamps: dict[str, Any] = {}
    for cell_id, head in zip(cell_ids, heads, strict=False):
        stamp = None
        if head:
            # Scan a small head window for the newest event with a parseable timestamp:
            # some events carry their timestamp only inside ``part`` (the head element is
            # one such shape), and a None stamp would age-unknown a live cell forever.
            for raw in head[:8]:
                try:
                    event = json.loads(raw) if isinstance(raw, str) else raw
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                part = event.get("part") if isinstance(event.get("part"), dict) else {}
                stamp = _event_timestamp(event, part)
                if stamp is not None:
                    break
        stamps[cell_id] = stamp
    return stamps


def _phase_published_at(parsed) -> Any:
    """Return the phase's own published-at stamp, tolerating legacy field names."""
    for key in ("published_at", "timestamp", "ts", "created_at"):
        value = parsed.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            return value
    return None


def _parse_phases(payloads, *, tails=None, now=None) -> dict[str, dict[str, Any]]:
    """Decode the ``story_phase`` hash into live-dimension phase entries.

    Each value is a JSON object written by ``LivePublisher.set_phase``. A malformed
    or empty entry is dropped (the badge is display-only), so a partial write can
    never affect the matrix status contract.

    Every surviving entry gains the live dimension:

      * ``last_phase_ts`` — the newer of the phase's own ``published_at`` stamp and
        the runner-telemetry tail timestamp (``tails``), normalized to UTC ISO, or
        ``None`` when neither exists (age-unknown).
      * ``age_seconds`` — whole seconds since ``last_phase_ts`` (0 for a future
        stamp), or ``None`` when no timestamp exists.
      * ``live`` — ``True`` exactly when a timestamp exists AND it falls within
        ``LIVE_WINDOW_SECONDS``. The window, not the publishing process, decides.
    """
    if now is None:
        now = _stamp_to_datetime(server._utc_now())
    if now is None:
        now = datetime.now(timezone.utc)
    tails = tails or {}
    phases: dict[str, dict[str, Any]] = {}
    for cell_id, raw in payloads.items():
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(parsed, dict) or not parsed.get("name"):
            continue
        candidates = [
            _stamp_to_datetime(_phase_published_at(parsed)),
            _stamp_to_datetime(tails.get(cell_id)),
        ]
        dated = [candidate for candidate in candidates if candidate is not None]
        last_dt = max(dated) if dated else None

        if last_dt is None:
            last_phase_ts = None
            age_seconds = None
        else:
            last_phase_ts = last_dt.isoformat(timespec="seconds").replace("+00:00", "Z")
            age_seconds = max(0, int((now - last_dt).total_seconds()))
        phases[cell_id] = {
            "name": parsed.get("name"),
            "index": parsed.get("index"),
            "total": parsed.get("total"),
            "live": (
                last_phase_ts is not None
                and age_seconds is not None
                and age_seconds <= LIVE_WINDOW_SECONDS
            ),
            "last_phase_ts": last_phase_ts,
            "age_seconds": age_seconds,
        }
    return phases
