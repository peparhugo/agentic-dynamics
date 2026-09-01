"""Docs-health routes — the read-only panel feed plus the controller's approve affordance.

Two routes, and the asymmetry between them is the whole design:

    GET  /api/docs-health          reads three durable files, writes nothing, connects to nothing
    POST /api/docs-health/approve  the ONE mutating call, through the existing mutation trust gate

``GET`` is a pure read by construction, not by convention. It never triggers a scan and never
touches the proposal, because a panel left open on a second monitor polls it every minute and a
dashboard poll must not be able to change the state it displays. If the panel wants fresher
numbers, the answer is the systemd timer (p2's cadence), not a side effect on a GET.

``POST`` reuses ``services.mutations._design_mutation_body`` + ``_idempotent_design_response`` —
the same loopback + same-origin + JSON + size-cap + ``Idempotency-Key`` boundary every other
Control Room mutation crosses, following the ``/api/flags/<id>/steer`` precedent of *reusing*
rather than duplicating it (the claude-agents pair is duplicated for a reason specific to that
feature's scope). The operation string namespaces this route's idempotency cache entries away
from every other mutation's.

**Two independent idempotence layers, and they guard different things.** This is worth being
explicit about, because it is the property the whole rail is built to protect:

    layer 1 (HTTP)    ``Idempotency-Key`` → Redis ``SET NX`` reserve/replay. Guards the
                      *transport*: a double-click, a retried fetch, a flaky connection replaying
                      the request. Same key + same body → the first response verbatim, and the
                      gate is never called twice.
    layer 2 (rail)    p3's ``O_EXCL`` claim on ``remediation.lock``. Guards the *work*: two
                      DIFFERENT keys, two browser tabs, a CLI ``docs gate approve`` racing the
                      portal. The kernel guarantees exactly one creator; every loser reports
                      ``already_in_flight`` and enqueues nothing.

Layer 1 alone would let two tabs with two keys launch two remediations. Layer 2 alone would make
an honest retry look like a second approval attempt. The contract needs both, and neither is
implemented here — this module's job is to make sure a browser request actually reaches them.
"""

from __future__ import annotations

from flask import Response, jsonify

from apps.control_room.services.context import ControlRoomServices
from apps.control_room.services.mutations import (
    _design_mutation_body,
    _idempotent_design_response,
)

#: The injected application context, bound by :func:`register` before any request is served.
_services: ControlRoomServices | None = None

#: Caps on the two free-text fields a controller signs with. Small on purpose: these are an
#: operator name and a one-line reason destined for an append-only audit file, not a document.
MAX_SIGNATURE_CHARS = 200
MAX_REASON_CHARS = 2_000

#: How the gate's outcome word maps onto HTTP.
#:
#: ``already_in_flight`` is deliberately 200, not 409. It is not a failed request — it is the
#: idempotence contract working exactly as designed: the second approval correctly declined to
#: launch a second run and reported so. That is p3's reasoning for exiting 0 on the same outcome
#: ("a rail that returned non-zero every time it correctly declined to act would train its
#: operator to ignore its exit code"), carried onto this surface: the response body says
#: ``enqueued: false`` and names the run that holds the claim, which is the honest answer.
#:
#: The state refusals are 409 (the request conflicts with the state the server holds — the same
#: code ``/api/flags/<id>/steer`` returns for a stale cell mapping). ``dispatch_failed`` is 503
#: and retryable: p3 rolls the claim back on a failed enqueue precisely so the rail stays
#: dispatchable, so telling the client "try again" is true rather than hopeful.
OUTCOME_STATUS = {
    "approved": 200,
    "dispatched": 200,
    "already_in_flight": 200,
    "refused_no_proposal": 409,
    "refused_stale_approval": 409,
    "refused_no_approval": 409,
    "refused_bad_workdir": 503,
    "refused_bad_mode": 400,
    "dispatch_failed": 503,
}

#: Outcomes after which the client should re-poll and try again rather than treat the proposal as
#: settled. Reported on the envelope so the panel does not have to hard-code the outcome list.
RETRYABLE_OUTCOMES = frozenset({"dispatch_failed"})


def api_docs_health() -> Response:
    """Serve the ``docs-health/v1`` envelope: the last scan, the flag, and the proposal.

    Always 200, including when the rail has never run. A panel that 500s because there is no
    scan on record would be reporting the panel's health rather than the docs', and an operator
    cannot tell an empty rail from a broken portal through a stack trace. The "nothing here yet"
    case is data (``available: false``, ``condition: "unmeasured"``), not an error.
    """
    envelope = _services.docs_health.load_docs_health(_services.docs_drift_results_dir)
    return jsonify(envelope)


def api_docs_health_approve() -> Response:
    """Record the controller's signature on the standing proposal, and launch it.

    Body (JSON):
        ``proposal_id`` (required) — the id the browser RENDERED. Echoing it back is what makes
            the affordance safe against the race this panel invites: the tab was open, the hourly
            timer fired, the inventory changed, and the button the operator is looking at now
            describes findings that are no longer the current ones. The gate refuses the mismatch
            (``refused_stale_approval``) instead of silently applying a signature to different
            work. It is required here even though p3 accepts ``None`` — a surface that let the
            client omit the check would make the check optional in practice.
        ``by`` (required) — who is signing. An unattributed approval is not an approval, it is a
            state change; p3 refuses to record one and so does this route.
        ``reason`` (optional) — free text, recorded with the signature in the audit trail.
        ``dispatch`` (optional, default true) — false signs now and launches later
            (``docs gate approve --no-dispatch``), for a controller who wants the signature on
            record before the worktree exists.

    The route validates the *shape* of the request and nothing else. Every rule that makes an
    approval safe — the state check, the id match, the claim — belongs to the gate, is enforced
    there, and is reported back through its ``outcome`` word verbatim. This surface owns no verb.
    """
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None

    proposal_id = body.get("proposal_id")
    signer = body.get("by")
    reason = body.get("reason", "")
    dispatch = body.get("dispatch", True)

    if not isinstance(proposal_id, str) or not proposal_id.strip():
        return jsonify({"error": "proposal_id is required — echo the id the panel rendered"}), 400
    if not isinstance(signer, str) or not signer.strip():
        return jsonify(
            {"error": "by is required — an unattributed approval is not an approval"}
        ), 400
    if len(signer) > MAX_SIGNATURE_CHARS:
        return jsonify({"error": f"by must be at most {MAX_SIGNATURE_CHARS} characters"}), 400
    if not isinstance(reason, str) or len(reason) > MAX_REASON_CHARS:
        return jsonify(
            {"error": f"reason must be a string of at most {MAX_REASON_CHARS} characters"}
        ), 400
    if not isinstance(dispatch, bool):
        return jsonify({"error": "dispatch must be a boolean"}), 400

    def approve() -> tuple[Response, int]:
        """Delegate to the gate and translate its decision, losing none of it."""
        decision = _services.docs_health.approve_proposal(
            by=signer.strip(),
            proposal_id=proposal_id.strip(),
            reason=reason.strip(),
            dispatch=dispatch,
            results_dir=_services.docs_drift_results_dir,
        )
        status = OUTCOME_STATUS.get(decision.outcome, 503)
        payload = decision.to_json()
        # Two derived conveniences on top of the gate's verbatim decision. Both are computed
        # from it rather than replacing any of it: the panel renders ``detail`` and ``outcome``
        # directly, and a client that wants the raw record still has every field.
        payload["ok"] = status == 200
        payload["retryable"] = decision.outcome in RETRYABLE_OUTCOMES
        return jsonify(payload), status

    # The operation string namespaces this route's idempotency entries. It carries the proposal
    # id so that the SAME Idempotency-Key reused against a DIFFERENT proposal cannot replay the
    # earlier proposal's cached response — a replay is only ever honest within one proposal.
    return _idempotent_design_response(f"docs-health-approve:{proposal_id}", body, approve)


def register(app, services: ControlRoomServices) -> None:
    """Register this module's routes on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/docs-health")(api_docs_health)
    app.post("/api/docs-health/approve")(api_docs_health_approve)
