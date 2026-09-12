"""Read the published website data (``apps/website/data.js``) for the scenario surfaces.

The EPM/energy scenario numbers and the escalation E_x table are DESIGN/EXTERNAL values whose
single published source is the generated site data (``build_data.py`` writes it; the file is
tracked in git). The Control Room serves them as LABELED scenarios, so it reads that published
file instead of re-deriving the numbers in a second place — one writer, one reader.

The file is a JS assignment (``window.DYNAMICS_DATA = { ... };``); parsing is strict: anything
that is not that shape raises :class:`PublishedDataError` and the caller names the degradation
(named unknown), never a silent empty scenario.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: The assignment whose right-hand side is the JSON payload.
_ASSIGNMENT = "window.DYNAMICS_DATA"


class PublishedDataError(ValueError):
    """The published data file is missing, malformed, or not the generated site data."""


def load_published_data(path: Path) -> dict[str, Any]:
    """Parse the generated website data at ``path``. Raises :class:`PublishedDataError`."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PublishedDataError(f"published data unreadable: {path} ({exc})") from None

    marker = text.find(_ASSIGNMENT)
    if marker < 0:
        raise PublishedDataError(
            f"not the published Dynamics data file (no {_ASSIGNMENT}): {path}"
        )
    assign = text.find("=", marker)
    if assign < 0:
        raise PublishedDataError(f"malformed published data (no assignment): {path}")

    body = text[assign + 1 :].strip()
    if body.endswith(";"):
        body = body[:-1].rstrip()
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise PublishedDataError(f"published data is not valid JSON: {path} ({exc})") from None
    if not isinstance(payload, dict):
        raise PublishedDataError(f"published data is not an object: {path}")
    return payload
