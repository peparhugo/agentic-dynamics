"""Agent-config rendering tests (refactor-repair P0-1).

Replaces the former byte-equality drift guard. The old guard asserted ``agent_config/`` is copied
verbatim into both ``.opencode/`` and ``.claude/`` — which guaranteed text drift would be caught
but left schema drift undetected: the two platforms do not share frontmatter schemas (opencode
agents use ``mode``/``model``/``permission``; Claude agents use ``name``/``description`` and hold
permissions at the project level) and index positional command args differently (opencode 1-indexed,
Claude 0-indexed). A byte-equal copy emits invalid Claude config while the test stayed green.

The new guard asserts instead:

1. **Per-target schema validity** — ``validate_opencode()``/``validate_claude()`` return no problems,
   including the explicit rejection of opencode-only keys (``mode``/``permission``/``temperature``/
   ``hidden`` on agents; ``agent``/``subtask`` on commands) in the Claude output.
2. **Meaning equivalence where platforms permit** — descriptions and body prose are preserved
   across the two renderings (only the schema projection and argument-index renumbering differ).
3. **Committed files match the renderers** — the two surfaces are regenerated from the semantic
   source, never hand-edited.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts import _gen_instructions as gen

ROOT = Path(__file__).resolve().parent.parent


def _render_opencode() -> dict[str, str]:
    return gen.render_opencode()


def _render_claude() -> dict[str, str]:
    return gen.render_claude()


def _body(content: str) -> str:
    """The document body (frontmatter stripped)."""
    _, body = gen._split_frontmatter(content)
    return body


def _description(fields: list[str]) -> str | None:
    return gen._scalar(fields, "description")


def _reindex_up(body: str) -> str:
    """Reverse the renderer's 1→0 arg reindex (Claude ``$N`` → opencode ``$N+1``)."""
    return re.sub(r"\$([0-9]+)", lambda m: "$" + str(int(m.group(1)) + 1), body)


# --- 1. per-target schema validity -------------------------------------------


def test_opencode_rendering_is_schema_valid():
    """The opencode rendering satisfies the opencode schema (required fields present)."""
    assert gen.validate_opencode(_render_opencode()) == []


def test_claude_rendering_is_schema_valid():
    """The Claude rendering satisfies the Claude schema (required fields present)."""
    assert gen.validate_claude(_render_claude()) == []


def test_claude_agents_reject_opencode_only_keys():
    """No opencode-only frontmatter key survives into a Claude agent (explicit check)."""
    for path, content in _render_claude().items():
        if not path.startswith(".claude/agents/"):
            continue
        fields, _ = gen._split_frontmatter(content)
        for key in ("mode", "permission", "temperature", "hidden"):
            assert not gen._has_top_level_key(fields, key), (
                f"{path}: opencode-only key {key!r} present in Claude agent"
            )
        model = gen._scalar(fields, "model")
        assert model is None or "/" not in model, (
            f"{path}: provider/model id {model!r} leaked into Claude agent"
        )


def test_claude_commands_reject_opencode_only_keys():
    """No opencode-only command frontmatter key survives into a Claude command."""
    for path, content in _render_claude().items():
        if not path.startswith(".claude/commands/"):
            continue
        fields, _ = gen._split_frontmatter(content)
        for key in ("agent", "subtask"):
            assert not gen._has_top_level_key(fields, key), (
                f"{path}: opencode-only key {key!r} present in Claude command"
            )


# --- 2. meaning equivalence where platforms permit ---------------------------


def test_rules_are_identical_across_surfaces():
    """Instruction docs are schema-free — the two surfaces carry byte-identical content."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.INSTRUCTIONS:
        assert oc[f".opencode/instructions/{name}"] == cl[f".claude/rules/{name}"], name


def test_skills_are_identical_across_surfaces():
    """Skills share a name/description schema — the two surfaces are byte-identical."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.SKILLS:
        assert (
            oc[f".opencode/skills/{name}/SKILL.md"] == cl[f".claude/skills/{name}/SKILL.md"]
        ), name


def test_agent_bodies_and_descriptions_are_equivalent():
    """Agents differ only in frontmatter projection; the prose and description are preserved."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.AGENTS:
        oc_fields, oc_body = gen._split_frontmatter(oc[f".opencode/agents/{name}.md"])
        cl_fields, cl_body = gen._split_frontmatter(cl[f".claude/agents/{name}.md"])
        assert oc_body == cl_body, f"{name}: agent body diverged between surfaces"
        assert _description(oc_fields) == _description(cl_fields), (
            f"{name}: agent description diverged between surfaces"
        )
        # The Claude name is the filename (derived), satisfying its required `name` field.
        assert gen._scalar(cl_fields, "name") == name, f"{name}: Claude agent name mismatch"


def test_command_descriptions_and_bodies_are_equivalent():
    """Commands differ only in arg renumbering; descriptions and prose are preserved."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.COMMANDS:
        oc_fields, oc_body = gen._split_frontmatter(oc[f".opencode/commands/{name}.md"])
        cl_fields, cl_body = gen._split_frontmatter(cl[f".claude/commands/{name}.md"])
        assert _description(oc_fields) == _description(cl_fields), (
            f"{name}: command description diverged between surfaces"
        )
        # Reversing the renderer's 1→0 reindex must recover the opencode body byte-for-byte.
        assert _reindex_up(cl_body) == oc_body, (
            f"{name}: command body diverged beyond positional-arg reindexing"
        )


# --- 3. committed files match the renderers (drift guard) ---------------------


def _committed_drift() -> list[str]:
    """Committed files that no longer match their renderer's output."""
    drift = []
    for rel, expected in {**_render_opencode(), **_render_claude()}.items():
        target = ROOT / rel
        if not target.exists():
            drift.append(f"{rel}: missing (not generated)")
        elif target.read_text(encoding="utf-8") != expected:
            drift.append(rel)
    return drift


def test_committed_surfaces_match_renderers():
    """Every committed surface file matches its renderer (regenerate on failure)."""
    drift = _committed_drift()
    assert not drift, (
        "generated surfaces drifted — regenerate with "
        "`python scripts/_gen_instructions.py`:\n" + "\n".join(sorted(drift))
    )


def test_surfaces_carry_no_orphan_files():
    """The generated trees contain no files outside the renderer mappings."""
    generated = {Path(rel) for rel in {**_render_opencode(), **_render_claude()}}
    orphaned = []
    for top in (
        Path(".opencode/instructions"),
        Path(".opencode/skills"),
        Path(".opencode/agents"),
        Path(".opencode/commands"),
        Path(".claude/rules"),
        Path(".claude/skills"),
        Path(".claude/agents"),
        Path(".claude/commands"),
    ):
        for p in (ROOT / top).rglob("*"):
            if p.is_file():
                rel = p.relative_to(ROOT)
                if rel not in generated:
                    orphaned.append(str(rel))
    assert not orphaned, (
        "orphan files in the generated surfaces (hand-added, not from agent_config/):\n"
        + "\n".join(sorted(orphaned))
    )
