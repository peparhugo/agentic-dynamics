"""AIO Control Agent definition guard (Wave-3 a4_aio_agent).

``a4`` lands ``.opencode/agents/aio-control.md`` — the AIO Control Agent, the controller's
delegated hands (all I/O converges there; all execution radiates from there; all in one).
``.opencode/agents/`` IS a generated surface (``scripts/_gen_instructions.py`` — the ``AGENTS``
manifest renders ``agent_config/agents/*.md`` onto both platforms), so the canonical source is
``agent_config/agents/aio-control.md`` and the two platform files are renderer projections,
never hand-edited.

The guard proves the a4 contract in both directions:

* **(a) the definition exists and states its contract** — the six contract points are present
  in the committed surface an opencode session actually loads, and the definition declares its
  role (the controller's proxy; the human is the controller, the AIO is the delegated hands).
* **(b) the surface handling is real** — the agents dir IS generated (verified which), the new
  agent is declared in the generator's manifest, the committed twins match the renderer
  projection, and the generator's ``--check`` stays green.
* **(c) the definition names the verified permanence commands** (``scripts/promote.py``,
  ``scripts/publish_release.py``) **and the ONE packet command**
  (``agentic-dynamics control status --json``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import _gen_instructions as gen

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "agent_config" / "agents" / "aio-control.md"
OC_AGENT = ROOT / ".opencode" / "agents" / "aio-control.md"
CL_AGENT = ROOT / ".claude" / "agents" / "aio-control.md"


def _oc_text() -> str:
    return OC_AGENT.read_text(encoding="utf-8")


# --- (a) the definition exists and states the contract -------------------------


def test_aio_control_definition_exists_on_both_platforms():
    """The agent is committed on every surface the generator owns."""
    for path in (SOURCE, OC_AGENT, CL_AGENT):
        assert path.is_file(), f"missing aio-control agent surface: {path}"


def test_aio_control_frontmatter_is_schema_valid():
    """The opencode agent declares description/mode/model and a permission block."""
    fields, _ = gen._split_frontmatter(OC_AGENT.read_text(encoding="utf-8"))
    assert gen._scalar(fields, "description"), "missing description"
    assert gen._scalar(fields, "mode"), "missing mode"
    assert gen._scalar(fields, "model"), "missing model"
    assert gen._has_top_level_key(fields, "permission"), "missing permission block"
    # The AIO is the session the controller operates THROUGH — a primary agent, not a
    # domain subagent spawned by another primary (the three domain agents are subagents).
    assert gen._scalar(fields, "mode") == "primary"


def test_aio_control_states_the_six_contract_points():
    """Every one of the six contract points is present in the loaded surface."""
    text = _oc_text()
    markers = [
        # 1 — the ONE packet at the start of every decision turn.
        "control status --json",
        "at the start of every decision turn",
        # 2 — act only on packet-returned identifiers.
        "run_ids / candidate_shas / gate_ids",
        "you do not act on it",
        # 3 — never infer live state from chat history (compaction-safe reload).
        "Never infer live workflow state from chat history",
        "reload the packet",
        # 4 — permanence through the verified commands, never a bypass of the gates.
        "verified commands",
        "Never raw",
        # 5 — never hand-edit generated surfaces.
        "Never hand-edit generated surfaces",
        # 6 — decisions are emitted; observable, never a silent authority.
        "observable",
        "never a silent authority",
    ]
    missing = [m for m in markers if m not in text]
    assert not missing, "aio-control misses contract markers:\n" + "\n".join(missing)


def test_aio_control_states_its_role_as_the_controllers_proxy():
    """The definition says the human is the controller and the AIO is the delegated hands."""
    text = _oc_text()
    for phrase in (
        "the human controller operates through",
        "The human is the controller",
        "delegated hands",
        "controller's proxy",
    ):
        assert phrase in text, f"aio-control missing role phrase: {phrase!r}"


# --- (c) the verified permanence commands + the packet command -----------------


def test_aio_control_names_the_verified_permanence_commands():
    """promote.py and publish_release.py are named — the ONLY paths to main / to publish."""
    text = _oc_text()
    for name in ("scripts/promote.py", "scripts/publish_release.py"):
        assert name in text, f"aio-control does not name the verified command: {name}"
    # The prohibition on bypassing the gates is explicit, not implied.
    assert "git push" in text
    assert "promote" in text and "publish" in text


def test_aio_control_names_the_packet_command():
    """The ONE control packet command is named verbatim (the machine surface)."""
    assert "agentic-dynamics control status --json" in _oc_text()


# --- (b) the surface handling is real ------------------------------------------


def test_agents_directory_is_generated_and_aio_control_is_declared():
    """a4 verified which side it was on: .opencode/agents IS generated (manifest + trees)."""
    assert "aio-control" in gen.AGENTS, "aio-control not registered in the generator manifest"
    assert ".opencode/agents" in gen.GENERATED_TREES
    assert ".claude/agents" in gen.GENERATED_TREES
    assert gen.render_opencode()[".opencode/agents/aio-control.md"] == SOURCE.read_text(
        encoding="utf-8"
    )


def test_committed_twins_match_the_renderer_projection():
    """The committed opencode + claude twins equal what the renderer emits from the source."""
    rendered = gen.render_all()
    assert OC_AGENT.read_text(encoding="utf-8") == rendered[".opencode/agents/aio-control.md"]
    assert CL_AGENT.read_text(encoding="utf-8") == rendered[".claude/agents/aio-control.md"]
    # The claude twin is the schema projection: name + description survive, the opencode-only
    # mode/permission/model keys are dropped.
    cl_fields, cl_body = gen._split_frontmatter(CL_AGENT.read_text(encoding="utf-8"))
    assert gen._scalar(cl_fields, "name") == "aio-control"
    for key in ("mode", "permission", "temperature", "hidden"):
        assert not gen._has_top_level_key(cl_fields, key), (
            f"opencode-only key {key!r} leaked into the claude twin"
        )
    # The body survives byte-for-byte across the projection.
    oc_fields, oc_body = gen._split_frontmatter(OC_AGENT.read_text(encoding="utf-8"))
    assert cl_body == oc_body
    assert gen._scalar(cl_fields, "description") == gen._scalar(oc_fields, "description")


def test_generator_check_stays_green():
    """The CI gate passes: no stale, missing, or orphaned generated surface."""
    drift = gen.find_drift()
    assert not drift, "generated surfaces drifted:\n" + "\n".join(drift)
