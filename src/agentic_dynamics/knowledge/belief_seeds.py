"""The seeded initial belief set (loop 2, phase s4c_belief_seeds).

Phase ``s4c_belief_seeds`` of the ``self_knowledge_layer`` workflow (design
``docs/designs/proposed/self_knowledge_layer.md``): the machine writes down, as durable
``source_type=belief`` records, what the measured history has taught it about itself operating.
The design doc's own example is the posterior "flash converges in ~1 wave on in-process work,
~4 on container seams" (design §"the Bayesian–frequentist synthesis") — a posterior that today
is held in-conversation and lost at compaction. This module is that posterior, minted ONCE from
the measured wave records + adversarial reviews (the citations), so a future AIO session starts
from its accumulated prior instead of re-deriving it by grep.

**The corpus.** :data:`SEEDS` holds FIVE hypotheses, each a canonical belief dict of the s4a
shape (``knowledge/belief_ingestion.py`` — ``{hypothesis, prior_confidence, n_confirmations,
n_disconfirmations, last_updated, evidence_class, domain, evidence_citations[]}``):

1. ``"flash converges in ~1 wave on in-process work"`` — the in-process convergence claim.
2. ``"container seams take ~4 waves"`` — the ``fleet_launch_*`` container-seam series.
3. ``"findings were opt-in and never produced"`` — ``kb_finding_layer``'s premise, now
   DISCONFIRMED by its own success (a pessimist seed, per the polarity note in
   ``knowledge/belief_update.py``).
4. ``"adversarial reviews catch wiring gaps tests miss"`` — the fleet series' adversarial
   record (n >= 6 by the fleet series).
5. ``"phases that ask for too much time out or false-positive"`` — the task-card lesson (the
   ``w2_revision_identity`` timeout + the deploy-gate false positives).

Each seed carries its measured-history citations (the wave names that bear on it, in the
``<spec> wave verdict [<run-id>]`` form the s4b trigger matches) and the confirmation counts the
measured history implies, so ``prior_confidence`` + the counts derive the seed's initial
standing confidence (``posterior_confidence``) through the s4a deterministic rule
(:func:`belief_ingestion.compute_posterior`). The counts and priors below are the AIO's honest
record at seed time, not a fitted optimum; each seed's comment states the counting convention so
a later reader can see exactly which measured events each count stands for.

**Scope fence: the seeds ONLY — no new types, no new operations.** Every record this module
derives is the existing ``belief``/``belief/v1`` family (the module re-exports the s4a
constants and delegates to :func:`belief_ingestion.derive_belief_record`); it adds NO new source
type and NO write/update/publish path — no import of ``belief_update`` (the s4b operation), no
``knowledge_stream`` handle, no outbox/registry write. Deriving the corpus is pure; persisting
it is a later phase's concern. The module is data + deterministic pure reads.

Actor + scope follow the s4a record: producer ``aio``, org-root ``org:<repository_id>`` scope
(structurally and in the payload), so a cell/workload retrieval can never resolve a seed belief
(the actor-layering rule the s7 adversarial phase probes). Domain is the retrieval axis the
deliverable's DONE_WHEN names — the seeds are retrievable by domain through
:func:`seeds_by_domain`.
"""

from __future__ import annotations

from typing import Any

from agentic_dynamics.knowledge import belief_ingestion as bi
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID

# ── Extractor contract constants (delegated — the corpus IS the s4a type) ──

#: The source_type every derived seed record carries. Delegated from the s4a type: the seeded
#: corpus is the SAME ``belief`` family the update protocol (s4b) reads, never a new record
#: class — a belief is a belief whether it was just minted or has absorbed twenty verdicts.
SOURCE_TYPE = bi.SOURCE_TYPE

#: The extractor version of every derived seed record (``belief/v1`` — the s4a generation).
EXTRACTOR_VERSION = bi.EXTRACTOR_VERSION

#: The actor of every derived seed record (``aio`` — the Bayesian engine's operator).
ACTOR = bi.ACTOR

# ── Domain constants (the retrieval axis of the DONE_WHEN) ───────────────

#: ``workstream-convergence`` — how many waves a workstream needs to converge. Holds the two
#: convergence seeds (seed 1 + seed 2), so a by-domain read of convergence beliefs returns both
#: the in-process and the container-seam claims together.
DOMAIN_WORKSTREAM_CONVERGENCE = "workstream-convergence"

#: ``producer-defaults`` — the opt-in-vs-default-on producer lesson (the ``k1`` finding-layer
#: lesson that loop 2's producers are always-on, not opt-in). Holds seed 3.
DOMAIN_PRODUCER_DEFAULTS = "producer-defaults"

#: ``adversarial-value`` — what independent adversarial reviews catch that the test gate misses.
#: Holds seed 4.
DOMAIN_ADVERSARIAL_VALUE = "adversarial-value"

#: ``phase-scoping`` — the task-card lesson: a phase whose card asks for too much times out or
#: trips a gate false-positive. Holds seed 5.
DOMAIN_PHASE_SCOPING = "phase-scoping"

#: The instant the corpus was minted — every seed's ``last_updated`` (its place on the revision
#: timeline). A fixed literal, like every other deterministic clock in the belief family, so the
#: corpus is rerun-safe: re-deriving the seeds on any later day yields byte-identical records
#: (the mint instant is HISTORY, never the derivation wall-clock).
SEED_TIMESTAMP = "2026-09-04T12:00:00+00:00"


# ── The seeded corpus ─────────────────────────────────────────────────────
#
# Each seed is a canonical belief dict. ``prior_confidence`` is the AIO's anchor — the
# confidence it would hold with NO measured evidence, kept at the doctrine-default 0.5 for every
# seed so the counts alone carry the information (an honest base, never a hand-won posterior).
# The counts encode the measured history the citations name. ``evidence_class`` is ``"[M]"`` —
# these seeds rest on measured wave records + reviews, not on the AIO's say-so; the class is
# REPORTED in the body and never elevates the record's own ADVISORY tier (the s4a rule).
SEEDS: tuple[dict[str, Any], ...] = (
    {
        # Seed 1 — the in-process convergence claim (design §"the Bayesian–frequentist
        # synthesis": "flash converges in ~1 wave on in-process work"). Three confirming
        # observations: engine_gaps_followups and kb_finding_layer each merged after ONE
        # flash workflow run (all phases ok, first attempt), and the in-flight
        # self_knowledge_layer wave has converged 10/10 phases first-pass on the first attempt.
        # One disconfirming observation: authoring_product_aio churned across 7 runs — recorded
        # honestly (its phases DID not converge in one wave), though its measured cause was the
        # systemic false-green + deploy-gate defects (git 3caad3765), not the model.
        "hypothesis": "flash converges in ~1 wave on in-process work",
        "prior_confidence": 0.5,
        "n_confirmations": 3,
        "n_disconfirmations": 1,
        "last_updated": SEED_TIMESTAMP,
        "evidence_class": "[M]",
        "domain": DOMAIN_WORKSTREAM_CONVERGENCE,
        "evidence_citations": [
            "engine_gaps_followups wave verdict run-2d9c9c53be34",
            "kb_finding_layer wave verdict run-77f7b899f4f8",
            "self_knowledge_layer wave verdict run-c8d98f56a124",
            "authoring_product_aio wave verdict run-f0844b583ef3",
        ],
    },
    {
        # Seed 2 — the container-seam convergence claim ("~4 on container seams"). The
        # measured instance is the fleet_launch series: FOUR sequential waves — boundary
        # (run-a8cd0180841c), boundary_followups (run-f114d4c43ff2), smoke (run-82800f7b4649),
        # container_smoke (run-6bd836f71f01) — before the container tier ran end-to-end (the
        # cs3 smoke) and the wave merged. Each wave's adversarial review certified the prior
        # wave's seams still unwired, so the series IS the counting event: n_confirmations=1
        # (one series converged at ~4 waves), all four wave verdicts cited as the evidence.
        "hypothesis": "container seams take ~4 waves",
        "prior_confidence": 0.5,
        "n_confirmations": 1,
        "n_disconfirmations": 0,
        "last_updated": SEED_TIMESTAMP,
        "evidence_class": "[M]",
        "domain": DOMAIN_WORKSTREAM_CONVERGENCE,
        "evidence_citations": [
            "fleet_launch_boundary wave verdict run-a8cd0180841c",
            "fleet_launch_boundary_followups wave verdict run-f114d4c43ff2",
            "fleet_launch_smoke wave verdict run-82800f7b4649",
            "fleet_launch_container_smoke wave verdict run-6bd836f71f01",
        ],
    },
    {
        # Seed 3 — kb_finding_layer's premise, phrased pessimistically (its own spec preamble:
        # the KB held 38,680 fact rows + code chunks but NO distilled findings — emit was
        # opt-in and default OFF). The premise HELD for loop 1's layer; the wave then made the
        # producer default-on and PRODUCED (k2's 164 backfilled wave findings + the k6 witness
        # phase finding under default settings), disconfirming the premise by its own success.
        # This is the pessimist seed belief_update.py names: a GREEN kb_finding_layer outcome
        # DISCONFIRMS it (the AIO's polarity judgment), encoded here as n_disconfirmations=1.
        "hypothesis": "findings were opt-in and never produced",
        "prior_confidence": 0.5,
        "n_confirmations": 0,
        "n_disconfirmations": 1,
        "last_updated": SEED_TIMESTAMP,
        "evidence_class": "[M]",
        "domain": DOMAIN_PRODUCER_DEFAULTS,
        "evidence_citations": [
            "kb_finding_layer wave verdict run-77f7b899f4f8",
        ],
    },
    {
        # Seed 4 — the adversarial record ("n >= 6 by the fleet series"). The four fleet
        # adversarial reviews each re-verified the test gate GREEN at the same commit where it
        # found real defects: EIGHT strict wiring gaps tests missed (b4-F1 clone-not-mounted
        # seam / b4-F2 shared-rw surface / b4-F3 in-process broker / b4-F5 phantom gate target,
        # fb4-F1 clone-still-unwired / fb4-F2 broker-refuses-container, ws5-F1 orchestrator-
        # refuses-own-spawn, cs4-F1 runs-root-not-reconciled). Each gap is ONE confirmation
        # that adversarial reviews catch what the green suite misses: n_confirmations=8.
        "hypothesis": "adversarial reviews catch wiring gaps tests miss",
        "prior_confidence": 0.5,
        "n_confirmations": 8,
        "n_disconfirmations": 0,
        "last_updated": SEED_TIMESTAMP,
        "evidence_class": "[M]",
        "domain": DOMAIN_ADVERSARIAL_VALUE,
        "evidence_citations": [
            "fleet_launch_boundary wave verdict run-a8cd0180841c",
            "fleet_launch_boundary_followups wave verdict run-f114d4c43ff2",
            "fleet_launch_smoke wave verdict run-82800f7b4649",
            "fleet_launch_container_smoke wave verdict run-6bd836f71f01",
        ],
    },
    {
        # Seed 5 — the task-card lesson ("phases that ask for too much time out or
        # false-positive"): a phase whose card asks for too much fails one of two measured ways.
        # Confirming observations: the w2_revision_identity phase of engine_gaps_verifier_revision
        # (run-85f33d68de3b) — a FOUR-part deliverable in one 7200s card — timed out ("Timeout
        # after 7200s", ledger 20260902T163439Z.json) and split the run; and the authoring
        # phases killed by deploy-gate false positives (a2_examples run-f0844b583ef3,
        # a4_aio_agent run-8cc5f04ac947, a6_adversarial run-29e658e4a011 — each DEPLOY_GATE-fired
        # on content that merely QUOTED a deploy). The construction-crew remedy (one small
        # deliverable per task card, workflow YAML :8-10) is the same wave's measured response.
        "hypothesis": "phases that ask for too much time out or false-positive",
        "prior_confidence": 0.5,
        "n_confirmations": 4,
        "n_disconfirmations": 0,
        "last_updated": SEED_TIMESTAMP,
        "evidence_class": "[M]",
        "domain": DOMAIN_PHASE_SCOPING,
        "evidence_citations": [
            "engine_gaps_verifier_revision wave verdict run-85f33d68de3b",
            "authoring_product_aio wave verdict run-f0844b583ef3",
            "authoring_product_aio wave verdict run-8cc5f04ac947",
            "authoring_product_aio wave verdict run-29e658e4a011",
        ],
    },
)


# ── Deterministic pure reads (the DONE_WHEN: retrievable by domain) ──────


def seed_domains() -> tuple[str, ...]:
    """The distinct domains the seeded corpus spans, in first-appearance order.

    The domains are the s4c retrieval axis (a by-domain read resolves the beliefs that bear on
    one operating question). Order is the corpus's own first-appearance order — deterministic,
    so a caller rendering the domains never sees a set-ordering surprise.
    """
    seen: list[str] = []
    for seed in SEEDS:
        domain = str(seed["domain"])
        if domain not in seen:
            seen.append(domain)
    return tuple(seen)


def seeds_by_domain(domain: str) -> tuple[dict[str, Any], ...]:
    """Every seed in ``domain``, in corpus order — the "retrievable by domain" read.

    Returns shallow copies of the canonical dicts so a caller can annotate a retrieved seed
    without corrupting the corpus (the counts/citations a later update advances are written as
    new belief versions, never by mutating this module's data). An unknown domain — including
    ``""``, which is never a valid belief domain — yields an empty tuple, the honest "no
    beliefs in that domain yet" state, never a fabricated row.
    """
    return tuple(dict(seed) for seed in SEEDS if seed["domain"] == domain)


def derive_seed_records(*, repository_id: str = REPOSITORY_ID) -> tuple[Any, ...]:
    """Derive the belief records for the whole corpus, in :data:`SEEDS` order.

    Delegates each seed dict to the s4a type (:func:`belief_ingestion.derive_belief_record`), so
    every corpus record carries the standard identity + actor/scope + the deterministic
    posterior (prior + counts → ``posterior_confidence``) and is rerun-safe — the same input
    always yields the same ``knowledge_id``/``entity_id``. Pure: nothing is written anywhere.
    ``repository_id`` defaults to the org id (the corpus is the AIO's org-root belief set), and
    may be redirected exactly as the type allows.
    """
    return tuple(
        bi.derive_belief_record(seed, repository_id=repository_id) for seed in SEEDS
    )
