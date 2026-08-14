"""Small native-v2 HTTP client for portal-owned OpenCode sessions.

The Control Room backend uses raw HTTP because it is already a Python process;
adding a Node SDK bridge would create another service and expose no additional
API guarantees.  The browser never receives the OpenCode server address.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

MAX_HTTP_BODY_BYTES = 2_000_000
MAX_SSE_EVENT_BYTES = 2_000_000


@dataclass
class OpenCodeError(RuntimeError):
    """Actionable failure returned by or encountered while calling OpenCode."""

    message: str
    status: int = 502

    def __str__(self) -> str:
        return self.message


class OpenCodeClient:
    """Call the native OpenCode v2 session and durable-event endpoints."""

    def __init__(self, base_url: str, *, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _json_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        """Issue one bounded JSON request and reject malformed success bodies."""
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=payload, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - configured loopback service
                raw = response.read(MAX_HTTP_BODY_BYTES + 1)
        except HTTPError as error:
            detail = error.read().decode(errors="replace").strip()
            raise OpenCodeError(
                f"OpenCode rejected the request ({error.code}): {detail or error.reason}",
                error.code,
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise OpenCodeError(f"OpenCode is unavailable: {error}") from error

        if len(raw) > MAX_HTTP_BODY_BYTES:
            raise OpenCodeError("OpenCode JSON response exceeded the 2000000-byte limit")
        if allow_empty and not raw.strip():
            return {}
        try:
            result = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise OpenCodeError("OpenCode returned malformed JSON") from error
        if not isinstance(result, dict):
            raise OpenCodeError("OpenCode returned an unexpected JSON response")
        return result

    def create_session(self, *, location: str, model: str) -> dict[str, Any]:
        """Create a native session bound to an approved repository location."""
        return self._json_request("POST", "/api/session", {"location": location, "model": model})

    def send_input(self, session_id: str, prompt: str, *, delivery: str) -> dict[str, Any]:
        """Queue or steer one durable prompt into an existing native session."""
        encoded = quote(session_id, safe="")
        return self._json_request(
            "POST",
            f"/api/session/{encoded}/prompt",
            {"prompt": prompt, "delivery": delivery},
        )

    def interrupt(self, session_id: str) -> dict[str, Any]:
        """Request interruption of active work without detaching the browser."""
        encoded = quote(session_id, safe="")
        return self._json_request("POST", f"/api/session/{encoded}/interrupt", {}, allow_empty=True)

    def messages(self, session_id: str) -> dict[str, Any]:
        """Return the native projected message history for explicit recovery."""
        encoded = quote(session_id, safe="")
        return self._json_request("GET", f"/api/session/{encoded}/message")

    def iter_events(self, session_id: str, *, after: str | None = None) -> Iterator[dict[str, Any]]:
        """Yield JSON objects from one native durable SSE subscription.

        SSE ``id`` is retained as ``_sse_id`` when the JSON body does not carry
        an aggregate sequence.  Multi-line data fields are joined according to
        the SSE framing rules, while comments and unknown fields are ignored.
        """
        encoded = quote(session_id, safe="")
        query = f"?{urlencode({'after': after})}" if after else ""
        request = Request(
            f"{self.base_url}/api/session/{encoded}/event{query}",
            headers={"Accept": "text/event-stream"},
            method="GET",
        )
        try:
            response = urlopen(request, timeout=max(self.timeout, 65.0))  # noqa: S310 - configured service
        except HTTPError as error:
            detail = error.read().decode(errors="replace").strip()
            raise OpenCodeError(
                f"OpenCode event stream failed ({error.code}): {detail or error.reason}",
                error.code,
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise OpenCodeError(f"OpenCode event stream is unavailable: {error}") from error

        content_type = response.headers.get_content_type()
        if content_type != "text/event-stream":
            response.close()
            raise OpenCodeError(f"OpenCode event stream returned {content_type}, not text/event-stream")

        data_lines: list[str] = []
        data_size = 0
        event_id: str | None = None
        try:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if line == "":
                    if data_lines:
                        raw_data = "\n".join(data_lines)
                        try:
                            event = json.loads(raw_data)
                        except json.JSONDecodeError:
                            event = {"type": "raw", "data": raw_data}
                        if not isinstance(event, dict):
                            event = {"type": "raw", "data": event}
                        if event_id and not any(key in event for key in ("sequence", "aggregateSequence")):
                            event["_sse_id"] = event_id
                        yield event
                    data_lines = []
                    data_size = 0
                    event_id = None
                    continue
                if line.startswith(":"):
                    continue
                field, _, value = line.partition(":")
                value = value[1:] if value.startswith(" ") else value
                if field == "data":
                    data_lines.append(value)
                    data_size += len(value.encode(errors="replace"))
                    if data_size > MAX_SSE_EVENT_BYTES:
                        raise OpenCodeError("OpenCode SSE event exceeded the 2000000-byte limit")
                elif field == "id":
                    event_id = value
        finally:
            response.close()
