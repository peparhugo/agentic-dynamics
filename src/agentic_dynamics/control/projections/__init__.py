"""The Control Room's read-only projection layer (d5-signed staging, d3 backend spec).

Pure derivations over already-emitted planes — one module per projection, each exposing
``build_<name>(deps, *, now, ...)`` with injected inputs (deterministic for a fixed fixture,
the same contract as ``control.control_status.build_packet``). The room's routes are thin
shells over these builders; nothing here writes Redis, the control DB, or the KB.

The loaders (``load_*``) are the modules' only IO, kept beside their builders so the script
renderers and the room consume the SAME derivation (one fact, one writer).

Projections in this package:

* ``model_quality`` (P3, step 6) — Grit / first-pass / narration / coverage.
* ``story_arc`` (P4, step 6) — the per-story session arc (snowball / velocity / β).
* ``run_value`` (P5, step 6) — observed-only accepted outcomes and cost per accepted outcome.
* ``arm_comparison`` (P6, step 6) — the compare/adapt arm ranking over real executed phases.
* ``sla_queue`` (P8, step 7) — queue depth, measured completion burn, the 2× depth rule.
* ``escalation`` (P9, step 7) — the cascade surface: no events invented, E_x labeled.
* ``batch`` (P10, step 7) — explicitly not-measurable; the rule-6 scenario, never a fraction.
* ``energy`` (rule 4, step 7) — EPM/energy scenario sources + the named measured gap.
"""

from agentic_dynamics.control.projections.arm_comparison import (
    SCHEMA as ARM_COMPARISON_SCHEMA,
)
from agentic_dynamics.control.projections.arm_comparison import (
    build_arm_comparison,
    load_phase_outcomes,
)
from agentic_dynamics.control.projections.batch import SCHEMA as BATCH_SCHEMA
from agentic_dynamics.control.projections.batch import build_batch
from agentic_dynamics.control.projections.energy import SCHEMA as ENERGY_SCHEMA
from agentic_dynamics.control.projections.energy import build_energy
from agentic_dynamics.control.projections.escalation import (
    SCHEMA as ESCALATION_SCHEMA,
)
from agentic_dynamics.control.projections.escalation import (
    build_escalation_cascade,
    load_escalation_attempts,
)
from agentic_dynamics.control.projections.model_quality import (
    SCHEMA as MODEL_QUALITY_SCHEMA,
)
from agentic_dynamics.control.projections.model_quality import (
    build_model_quality,
    load_workflow_attempts,
)
from agentic_dynamics.control.projections.run_value import (
    SCHEMA as RUN_VALUE_SCHEMA,
)
from agentic_dynamics.control.projections.run_value import (
    build_run_value,
)
from agentic_dynamics.control.projections.sla_queue import SCHEMA as SLA_QUEUE_SCHEMA
from agentic_dynamics.control.projections.sla_queue import (
    build_sla_queue,
    load_breach_views,
)
from agentic_dynamics.control.projections.story_arc import (
    SCHEMA as STORY_ARC_SCHEMA,
)
from agentic_dynamics.control.projections.story_arc import (
    build_story_arc,
)

__all__ = [
    "ARM_COMPARISON_SCHEMA",
    "BATCH_SCHEMA",
    "ENERGY_SCHEMA",
    "ESCALATION_SCHEMA",
    "MODEL_QUALITY_SCHEMA",
    "RUN_VALUE_SCHEMA",
    "SLA_QUEUE_SCHEMA",
    "STORY_ARC_SCHEMA",
    "build_arm_comparison",
    "build_batch",
    "build_energy",
    "build_escalation_cascade",
    "build_model_quality",
    "build_run_value",
    "build_sla_queue",
    "build_story_arc",
    "load_breach_views",
    "load_escalation_attempts",
    "load_phase_outcomes",
    "load_workflow_attempts",
]
