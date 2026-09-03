"""Producer-side belief-record derivation for the self-knowledge layer (loop 2).

The belief record is phase ``s4a_belief_record_type``'s substrate (``self_knowledge_layer``
wave, design ``docs/designs/proposed/self_knowledge_layer.md``): a hypothesis the machine
holds about itself operating, tracked with confirmation counts and a posterior confidence —
"flash converges in ~1 wave on in-process work, ~4 on container seams" is a posterior currently
held in-conversation and lost at compaction (prereg Edge 4). This module is the record TYPE
both the update protocol (s4b) and the seeded initial belief set (s4c) ride on; it derives ONE
``source_type=belief`` KnowledgeRecord from a belief dict carrying the deliverable's fixed
content shape::

    {hypothesis, prior_confidence, n_confirmations, n_disconfirmations,
     last_updated, posterior_confidence, evidence_class, domain,
     evidence_citations[]}

plus the context-abstraction dimensions (``actor`` + ``scope``).

**The Bayesian–frequentist contract.** A belief starts from a prior (the doctrine + the
evidence_class ladder — ``[P]`` policy / ``[M]`` measured / ``[C]`` derived / ``[H]``
heuristic, "a prior-authority ladder by construction") and is revised by frequentist evidence
(wave outcomes) as it accumulates. ``prior_confidence`` is the confidence the AIO held before
the recorded evidence arrived; ``posterior_confidence`` is the confidence implied by that
prior PLUS the recorded confirmation counts — the two converge as evidence accumulates. The
record carries BOTH because the prior anchors the belief's history (s4b revises it forward as
new verdicts land) while the posterior is where the belief stands today;
for a fresh hypothesis (``n_confirmations == n_disconfirmations == 0``) they are equal by
construction. :func:`compute_posterior` is the type's deterministic well-formedness rule — a
Beta-binomial mean update where the prior counts as :data:`PRIOR_PSEUDO_COUNT` pseudo-
observations — so a belief dict that omits ``posterior_confidence`` still yields a
self-consistent record, and s4b's in-place update (``n_confirmations +1`` /
``n_disconfirmations +1``, posterior recomputed from the SAME rule) never has to re-derive the
math. An explicit ``posterior_confidence`` in the input overrides the computed default, so a
caller can record a hand-set posterior without fighting the engine.

``evidence_class`` in the body is the belief's OWN declared class of backing evidence, drawn
from the ladder and validated against it. It is a REPORTED description of what the belief
rests on (the ``[M]`` the s4c seeds will carry for their measured-history citations), NOT a
permission the writer grants itself: the record's KB-level authority is uniformly ``ADVISORY``
/ ``[H]`` (a belief is the AIO's self-reported posterior, exactly like a session close or a
decision), so a belief that *claims* ``[P]`` policy backing can never mint itself a POLICY-
tier KB row — self-reported evidence-class labels describe, they never self-elevate.

Actor + scope follow the design's actor-layering table: the producer is the AIO and the record
lives in the AIO's org-root scope (``org:agentic-dynamics`` — the controller + AIO see it; the
controller model is an org-root belief class the AIO reads, never a cell agent). Structurally
the record keeps the org id as ``repository_id`` and ``org:<repository_id>`` as ``acl_scope``
(the same anchoring the session/decision siblings use), so ``retrieval.scope_excluded``'s hard
pre-filter keeps every ``self-*`` cell and foreign workload from resolving it; only an explicit
org-root read sees it. The ``actor`` key travels in the payload (self-describing — the KB
schema has no actor field).

Identity: ONE logical entity per hypothesis. ``belief_id`` is ``sha256(domain|hypothesis)``
(the ``domain`` groups beliefs for the s4c "retrievable by domain" read); ``logical_locator``
is that id and ``source_uri`` is ``belief:<belief_id>`` — a family distinct from
``session:<slug>`` / ``decision:<id>`` / ``wave_verdict:<run_id>`` / ``wave:<name>``.
``entity_id`` is therefore STABLE across updates of the same hypothesis: when s4b confirms or
disconfirms, the changed counts + advanced ``last_updated`` re-key ``knowledge_id`` while
``entity_id`` holds — the version chain the "updated in place, never duplicated" rule (s4b)
needs — while two different hypotheses (or the same words in different domains) never
collide. ``revision`` is :data:`REVISION_FALLBACK` (the record is the AIO's org-root
posterior, not bound to one commit — folding HEAD in would re-key every belief as HEAD moves).

Scope fence: the TYPE ONLY — derivation + record construction + the deterministic posterior
rule. The UPDATE operation (mutating an existing belief when a wave outcome bears on it) is s4b
(``knowledge/belief_update.py`` — the in-place update + its wave-verdict trigger); the seeded
corpus is s4c; nothing here writes to the KB or registers a command. ``build_belief_record``
carries the one s4b affordance this type must own — the ``supersedes`` version link, folded
into ``extra_fields`` before the content hash is computed (see its docstring).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from agentic_dynamics.knowledge.knowledge import (
    Authority,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
from agentic_dynamics.knowledge.record_factory import build_record as build_record_from_parts
from agentic_dynamics.knowledge.session_ingestion import aio_acl_scope

# ── Extractor contract constants ────────────────────────────────

#: ``source_type`` recorded on every belief record — registered in ``knowledge.SOURCE_TYPES``
#: as an observation-family ADVISORY/``[H]`` row: a belief is a hypothesis the machine holds
#: about itself operating (the Bayesian engine of loop 2), never an instruction to act.
SOURCE_TYPE = "belief"

#: The extractor generation. ``knowledge_id`` folds this in, so the belief family is
#: identity-distinct from every sibling producer (session/``meta_session``, ``decision``,
#: ``wave_verdict``, ``observation``) even for byte-identical bodies. A literal — stability is
#: the point.
EXTRACTOR_VERSION = "belief/v1"

#: The producer/actor of every belief record. The AIO is the Bayesian engine's operator; the
#: value travels in the payload (self-describing — the KB schema has no ``actor`` field).
ACTOR = "aio"

#: Fallback ``source_revision`` for a belief record. The record is the AIO's org-root posterior,
#: NOT bound to one commit — folding the checkout HEAD in as ``revision`` would re-key every
#: belief as HEAD moves. Mirrors ``session_ingestion.REVISION_FALLBACK``.
REVISION_FALLBACK = "belief/unrevisioned"

#: The evidence_class ladder the belief's ``evidence_class`` content field draws from
#: (design §"the Bayesian–frequentist synthesis"): ``[P]`` policy / ``[M]`` measured /
#: ``[C]`` derived / ``[H]`` heuristic — "a prior-authority ladder by construction". A belief
#: DECLARES its backing class from this ladder; the declaration is reported in the body and
#: validated here (``[X]`` external is deliberately absent — loop-2 beliefs about this machine
#: operating rest on this machine's own doctrine + measurements, never on outside claims).
EVIDENCE_LADDER = ("[P]", "[M]", "[C]", "[H]")

#: The class a belief carries when the caller declares none — the honest base of the ladder: an
#: undeclared hypothesis is a heuristic until evidence says otherwise (the s4c seeds declare
#: their ``[M]`` measured backing explicitly).
DEFAULT_EVIDENCE_CLASS = "[H]"

#: The prior's weight in pseudo-observations for :func:`compute_posterior`. A value of 2.0
#: makes one real observation move a 0.5 prior to 0.667 (confirm) / 0.333 (disconfirm) — a
#: weakly-held prior that the wave evidence visibly revises, neither a rigid dogma (large
#: pseudo-count) nor a coin-flip that a single datum shatters (small). ``[H]`` — a heuristic
#: constant, deterministic and documented, not fitted.
PRIOR_PSEUDO_COUNT = 2.0

#: The content fields the deliverable fixes (plus ``actor``/``scope``). The list is
#: documentation — the derivation below builds exactly these keys — so a reader can see at a
#: glance what a belief record carries.
CONTENT_FIELDS = (
    "hypothesis",
    "prior_confidence",
    "n_confirmations",
    "n_disconfirmations",
    "last_updated",
    "posterior_confidence",
    "evidence_class",
    "domain",
    "evidence_citations",
)


# ── Small deterministic helpers ─────────────────────────────────


def _required_value(belief: dict[str, Any], field: str, label: str) -> str:
    """Return a required content field, stripping whitespace.

    Raises ``ValueError`` when the field is missing or empty — a belief with no ``hypothesis``
    (its subject), no ``domain`` (its retrieval axis), or no ``last_updated`` (its place on
    the revision timeline) cannot be registered.
    """
    value = str(belief.get(field) or "").strip()
    if not value:
        raise ValueError(f"belief has no {label!r} — cannot derive a belief record")
    return value


def _confidence_value(
    belief: dict[str, Any], field: str, label: str, *, default: float | None = None
) -> float:
    """Return a confidence-valued content field as a ``float`` in ``[0, 1]``.

    Accepts an ``int``/``float`` (never a ``bool``) or a numeric string; anything else — or a
    value outside ``[0, 1]``, which would silently corrupt the posterior math — raises
    ``ValueError``. ``default`` is returned when the field is absent.
    """
    value = belief.get(field, default)
    if value is None:
        raise ValueError(f"belief has no {label!r} — cannot derive a belief record")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"belief {label!r} must be a number in [0, 1], got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"belief {label!r} must be a number in [0, 1], got {value!r}") from None
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"belief {label!r} must be in [0, 1], got {number!r}")
    return number


def _count_value(belief: dict[str, Any], field: str, label: str) -> int:
    """Return a confirmation/disconfirmation count as a non-negative ``int``.

    Missing/``None`` → ``0`` (a fresh hypothesis has counted no outcomes). A fractional or
    boolean count is a caller error (half a confirmation is not evidence), raised loudly
    rather than silently coerced.
    """
    value = belief.get(field, 0)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"belief {label!r} must be a non-negative int, got {value!r}")
    if value < 0:
        raise ValueError(f"belief {label!r} must be a non-negative int, got {value!r}")
    return value


def _list_value(belief: dict[str, Any], field: str) -> list[str]:
    """Normalize a list-valued content field to a deterministic ``list[str]``.

    ``None``/missing → ``[]``; a ``list``/``tuple`` is kept in CALLER order (the citations are
    the evidence in the order the AIO cites them) with each element coerced to ``str``. A bare
    string is treated as one item, not split.
    """
    value = belief.get(field)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _evidence_class_value(belief: dict[str, Any]) -> str:
    """Return the belief's declared evidence class, validated against :data:`EVIDENCE_LADDER`.

    Defaults to :data:`DEFAULT_EVIDENCE_CLASS` (the honest base of the ladder) when absent; a
    value outside the ladder — including ``[X]`` — is rejected loudly: a belief record must
    never carry an evidence class the design's ladder does not define.
    """
    value = str(belief.get("evidence_class") or DEFAULT_EVIDENCE_CLASS).strip().upper()
    if value not in EVIDENCE_LADDER:
        raise ValueError(
            f"belief evidence_class must be one of {EVIDENCE_LADDER} "
            f"(the prior-authority ladder), got {value!r}"
        )
    return value


def belief_id(domain: str, hypothesis: str) -> str:
    """Return a stable identity for ONE hypothesis (one belief entity).

    Folds ``domain`` deliberately — the same words under two domains are two different
    beliefs, and the domain is the s4c retrieval axis. Deliberately does NOT fold the counts
    or ``last_updated``: the identity names the hypothesis SLOT, so s4b's in-place update
    (counts change, ``last_updated`` advances) re-keys ``knowledge_id`` while ``entity_id``
    holds — the "updated in place, never duplicated" version chain. This is the ``belief_id``
    the durable records' ``logical_locator`` carries; the s4b belief index re-derives it from
    the payload's ``domain``/``hypothesis`` (the payload body has no ``logical_locator`` field),
    so the update trigger groups versions by the SAME identity the type names.
    """
    return hashlib.sha256(f"{domain}|{hypothesis}".encode()).hexdigest()[:16]


# ── The deterministic posterior rule (the type's well-formedness) ─


def compute_posterior(
    prior_confidence: float, n_confirmations: int, n_disconfirmations: int
) -> float:
    """Return the posterior confidence implied by ``prior_confidence`` + the counts.

    The type's deterministic well-formedness rule — a Beta-binomial mean update in which the
    prior counts as :data:`PRIOR_PSEUDO_COUNT` pseudo-observations::

        a = prior_confidence * PRIOR_PSEUDO_COUNT
        b = (1 - prior_confidence) * PRIOR_PSEUDO_COUNT
        posterior = (a + n_confirmations) / (a + b + n_confirmations + n_disconfirmations)

    A confirmation moves the posterior toward 1, a disconfirmation toward 0, and a fresh
    hypothesis (``0``/``0``) reproduces its prior exactly — "posterior moves toward the
    evidence with the confirmation count; a disconfirm lowers it" (s4b's update rule reads
    back through this same function, so the type and the update can never disagree on the
    math). The result is rounded to six decimals so two derivations of the same inputs always
    serialize to byte-identical bodies.

    ``prior_confidence`` must be in ``[0, 1]`` and the counts non-negative ``int``s (the same
    validation the derivation applies before calling); the denominator is always positive
    because ``PRIOR_PSEUDO_COUNT > 0``.
    """
    prior_confidence = float(prior_confidence)
    if isinstance(prior_confidence, bool) or not 0.0 <= prior_confidence <= 1.0:
        raise ValueError(f"prior_confidence must be in [0, 1], got {prior_confidence!r}")
    if isinstance(n_confirmations, bool) or not isinstance(n_confirmations, int):
        raise ValueError(
            f"n_confirmations must be a non-negative int, got {n_confirmations!r}"
        )
    if isinstance(n_disconfirmations, bool) or not isinstance(n_disconfirmations, int):
        raise ValueError(
            f"n_disconfirmations must be a non-negative int, got {n_disconfirmations!r}"
        )
    if n_confirmations < 0 or n_disconfirmations < 0:
        raise ValueError("n_confirmations/n_disconfirmations must be non-negative")
    a = prior_confidence * PRIOR_PSEUDO_COUNT
    b = (1.0 - prior_confidence) * PRIOR_PSEUDO_COUNT
    posterior = (a + n_confirmations) / (
        a + b + n_confirmations + n_disconfirmations
    )
    return round(posterior, 6)


# ── The canonical content payload ───────────────────────────────


def belief_payload(
    belief: dict[str, Any], *, repository_id: str = REPOSITORY_ID
) -> dict[str, Any]:
    """Return the canonical content payload for ONE belief record.

    Exactly the deliverable's content shape (normalized + validated) plus ``actor`` and
    ``scope`` — the record's context-abstraction dimensions. ``scope`` mirrors the record's
    own ``acl_scope`` (``aio_acl_scope(repository_id)``); ``actor`` is the module's ``ACTOR``
    literal. ``posterior_confidence`` is the caller's explicit value when given, else
    :func:`compute_posterior` applied to the (validated) prior + counts, so every record is
    self-consistent even for a dict that omits it. Confidences are rounded to six decimals so
    the body's floats serialize deterministically. This dict is what ``text`` serializes
    (sorted keys), so it is the entire hashed body: two derivations of the same belief dict
    yield byte-identical bodies and therefore identical ids (rerun-safe), while an updated
    count or an advanced ``last_updated`` yields a new body and a new ``knowledge_id`` for the
    same belief entity.
    """
    hypothesis = _required_value(belief, "hypothesis", "hypothesis")
    domain = _required_value(belief, "domain", "domain")
    last_updated = _required_value(belief, "last_updated", "last_updated")
    prior_confidence = round(
        _confidence_value(belief, "prior_confidence", "prior_confidence"), 6
    )
    n_confirmations = _count_value(belief, "n_confirmations", "n_confirmations")
    n_disconfirmations = _count_value(belief, "n_disconfirmations", "n_disconfirmations")
    evidence_class = _evidence_class_value(belief)

    posterior = belief.get("posterior_confidence")
    if posterior is None:
        posterior = compute_posterior(prior_confidence, n_confirmations, n_disconfirmations)
    else:
        posterior = round(
            _confidence_value(belief, "posterior_confidence", "posterior_confidence"), 6
        )

    return {
        "hypothesis": hypothesis,
        "prior_confidence": prior_confidence,
        "n_confirmations": n_confirmations,
        "n_disconfirmations": n_disconfirmations,
        "last_updated": last_updated,
        "posterior_confidence": posterior,
        "evidence_class": evidence_class,
        "domain": domain,
        "evidence_citations": _list_value(belief, "evidence_citations"),
        "actor": ACTOR,
        "scope": aio_acl_scope(repository_id),
    }


# ── Record construction ─────────────────────────────────────────


def build_belief_record(
    belief: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
    supersedes: str | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=belief`` record from a belief dict.

    ``belief`` is the hypothesis payload: ``{hypothesis, domain, last_updated,
    prior_confidence, evidence_class, n_confirmations, n_disconfirmations,
    posterior_confidence?, evidence_citations[]}`` — ``hypothesis``/``domain``/
    ``last_updated``/``prior_confidence`` required, the counts default ``0``,
    ``evidence_class`` defaults ``[H]``, ``posterior_confidence`` defaults to the computed
    posterior, ``evidence_citations`` defaults ``[]``. The record's ``text`` is the canonical
    JSON body from :func:`belief_payload` — deterministic, so ``content_hash``/``knowledge_id``
    are rerun-safe for identical input.

    Identity follows the canonical contract in :mod:`knowledge`:

    * ``logical_locator`` is the ``belief_id`` (hash of ``domain|hypothesis``); ``source_uri``
      is ``belief:<belief_id>`` — a family distinct from ``session:<slug>`` /
      ``decision:<id>`` / ``wave_verdict:<run_id>``, so a belief never collides on
      ``entity_id``.
    * ``revision`` is :data:`REVISION_FALLBACK` (the record is not bound to one commit;
      folding HEAD in would re-key every belief as the checkout advances).
    * ``entity_id = sha256(repository_id | source_uri | logical_locator)``; ``content_hash`` is
      the sha256 of the durable artifact; ``knowledge_id`` folds them with the revision + the
      ``belief/v1`` extractor. Re-deriving the SAME belief dict is a no-op; an s4b update
      (counts changed, ``last_updated`` advanced) re-keys ``knowledge_id`` while ``entity_id``
      holds — a new version of the SAME hypothesis slot, exactly the supersede-capable spine
      the "updated in place, never duplicated" rule needs.

    ``authority`` is ``ADVISORY`` / ``[H]`` — the registered nominal for ``belief``: a belief
    record is the AIO's self-reported posterior about the machine operating (like a session
    close or a decision), never an independent measurement, so it can inform the AIO's next
    operating choice but never override a MEASURED ledger row or pinned policy. The belief's
    DECLARED ``evidence_class`` (the ``[M]`` of a measured-history seed) travels in the body as
    a reported description of its backing evidence — it does not promote the record's own KB
    trust tier, which stays uniformly ADVISORY. ``repository_id`` defaults to the org id and
    ``acl_scope`` to the AIO org-root scope (see :func:`aio_acl_scope`). ``observed_at`` is the
    belief's own ``last_updated`` — the real "when this belief was last revised" — while
    ``valid_from``/``indexed_at`` stay the derivation/consumer clocks.

    ``supersedes`` (optional) names the predecessor ``knowledge_id`` this record is the new
    VERSION of — the s4b in-place update link. It is folded into ``extra_fields`` BEFORE the
    factory computes ``content_hash``, so the durable artifact (which serializes ``supersedes``
    verbatim) is exactly the bytes the hash covers; a caller that appends the link after
    construction would desynchronize the two. ``None`` (the default) omits the key, so a plain
    derivation keeps byte-identical ids to the pre-s4b records.

    Raises ``ValueError`` when the belief carries no ``hypothesis``/``domain``/``last_updated``,
    an out-of-range or non-numeric confidence, a fractional/negative count, or an
    ``evidence_class`` outside the ladder.
    """
    payload = belief_payload(belief, repository_id=repository_id)
    belief_key = belief_id(payload["domain"], payload["hypothesis"])
    scope = aio_acl_scope(repository_id)

    extra: dict[str, Any] = {
        # The belief record is not tied to a commit of its own — mirror the session/decision
        # producers, which pass commit_sha="" while folding their revision marker through the
        # `revision` input (record_factory's contract).
        "commit_sha": "",
        "extractor_version": EXTRACTOR_VERSION,
        "acl_scope": scope,
        # observed_at is the belief's own last_updated (when the belief was last revised),
        # not the derivation wall-clock; the artifact blanks it, so it never perturbs the
        # rerun-safe content hash.
        "observed_at": payload["last_updated"],
    }
    if supersedes is not None:
        # The s4b version link: the artifact carries it, the hash covers it, and the registry
        # closes the predecessor out at this record's valid_from (see outbox.registry_lines_for).
        extra["supersedes"] = supersedes

    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=f"belief:{belief_key}",
        logical_locator=belief_key,
        repository_id=repository_id,
        revision=REVISION_FALLBACK,
        authority=Authority.ADVISORY,
        evidence_class="[H]",
        text=json.dumps(payload, sort_keys=True),
        extra_fields=extra,
        now=now,
    )


def derive_belief_record(
    belief: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public derivation entry point — delegates to :func:`build_belief_record`.

    Deliberately singular (like the session/decision producers): one belief dict always yields
    exactly one belief record, with no batch pre-filter case. A belief missing its required
    fields is a genuine caller error, not a skip case.
    """
    return build_belief_record(belief, repository_id=repository_id, now=now)
