"""CAP I1–I3, I8, I9, I10 — the fact reducers package: the ``REDUCERS`` registry, its only public
surface.

Per design §4.1, reducers live here and are exposed through ONE surface — :data:`REDUCERS`
(``reducer_version`` → :class:`~agentic_dynamics.control.facts.ReducerSpec`) — so the
derivation-chain validator (``facts.verify_chain``) and a producer
(``scripts/kb_produce_facts.py``) both resolve the same declaration for a version string.

``REDUCERS`` maps version → spec (what ``verify_chain`` consults); :func:`get_reducer` maps
version → the pure callable (what a producer invokes). The two are kept in lockstep here so a
registered version always has a runnable implementation and vice versa.

``PROFILES_V1``/``profiles_v1`` (CAP addendum I8) live in ``control/profiles.py`` — that
increment's own reserved home (design §6) — not under this package's directory; they are
registered here, the same as every other reducer, so ``verify_chain`` and
``scripts/kb_produce_facts.py`` need only ever consult this one surface.

``PATTERN_V1``/``pattern_v1`` (CAP addendum I9, D7) and ``CHECKPOINT_V1``/``checkpoint_v1`` (CAP
addendum I10) DO live under this package (``control/reducers/{pattern,checkpoint}.py``) — the
design's own reserved-homes table (§6) puts both increments' reducers in the reducers package
proper, unlike I8's ``profiles.py``.
"""

from __future__ import annotations

from agentic_dynamics.control.facts import Reducer, ReducerSpec
from agentic_dynamics.control.profiles import PROFILES_V1, profiles_v1
from agentic_dynamics.control.reducers.attempt_facts import ATTEMPT_FACTS_V1, attempt_facts_v1
from agentic_dynamics.control.reducers.checkpoint import CHECKPOINT_V1, checkpoint_v1
from agentic_dynamics.control.reducers.job_facts import JOB_FACTS_V1, job_facts_v1
from agentic_dynamics.control.reducers.pattern import PATTERN_V1, pattern_v1
from agentic_dynamics.control.reducers.policy_facts import POLICY_FACTS_V1, policy_facts_v1
from agentic_dynamics.control.reducers.spec_status import SPEC_STATUS_V1, spec_status_v1
from agentic_dynamics.control.reducers.story_facts import STORY_FACTS_V1, story_facts_v1
from agentic_dynamics.control.reducers.workflow_facts import WORKFLOW_FACTS_V1, workflow_facts_v1

#: version → ReducerSpec — the declarative registry ``facts.verify_chain`` consumes.
REDUCERS: dict[str, ReducerSpec] = {
    SPEC_STATUS_V1.version: SPEC_STATUS_V1,
    ATTEMPT_FACTS_V1.version: ATTEMPT_FACTS_V1,
    JOB_FACTS_V1.version: JOB_FACTS_V1,
    WORKFLOW_FACTS_V1.version: WORKFLOW_FACTS_V1,
    POLICY_FACTS_V1.version: POLICY_FACTS_V1,
    STORY_FACTS_V1.version: STORY_FACTS_V1,
    PROFILES_V1.version: PROFILES_V1,
    PATTERN_V1.version: PATTERN_V1,
    CHECKPOINT_V1.version: CHECKPOINT_V1,
}

#: version → pure reducer callable — what ``scripts/kb_produce_facts.py`` invokes.
_IMPLS: dict[str, Reducer] = {
    SPEC_STATUS_V1.version: spec_status_v1,
    ATTEMPT_FACTS_V1.version: attempt_facts_v1,
    JOB_FACTS_V1.version: job_facts_v1,
    WORKFLOW_FACTS_V1.version: workflow_facts_v1,
    POLICY_FACTS_V1.version: policy_facts_v1,
    STORY_FACTS_V1.version: story_facts_v1,
    PROFILES_V1.version: profiles_v1,
    PATTERN_V1.version: pattern_v1,
    CHECKPOINT_V1.version: checkpoint_v1,
}


def get_reducer(version: str) -> Reducer | None:
    """Return the pure reducer callable for ``version``, or ``None`` when unregistered."""
    return _IMPLS.get(version)


__all__ = [
    "REDUCERS",
    "get_reducer",
    "SPEC_STATUS_V1",
    "spec_status_v1",
    "ATTEMPT_FACTS_V1",
    "attempt_facts_v1",
    "JOB_FACTS_V1",
    "job_facts_v1",
    "WORKFLOW_FACTS_V1",
    "workflow_facts_v1",
    "POLICY_FACTS_V1",
    "policy_facts_v1",
    "STORY_FACTS_V1",
    "story_facts_v1",
    "PROFILES_V1",
    "profiles_v1",
    "PATTERN_V1",
    "pattern_v1",
    "CHECKPOINT_V1",
    "checkpoint_v1",
]
