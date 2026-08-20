"""Drift guard (critique rec 6): the generated `.opencode/` + `.claude/` byte-match `agent_config/`.

`scripts/_gen_instructions.py` is the single writer of the two instruction surfaces. This test
calls its `render_surfaces()` — the *same* pure function the writer uses — and asserts the
committed files are byte-identical. A hand-edit to a generated file is a drift failure, never a
silent divergence between the two surfaces.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _render() -> dict[str, str]:
    """Import the generator and render the surface (no filesystem writes)."""
    from scripts import _gen_instructions

    return _gen_instructions.render_surfaces()


def test_generated_surfaces_match_agent_config():
    """Every committed `.opencode/`/`.claude/` instruction file byte-matches its agent_config/ source."""
    rendered = _render()
    assert rendered, "render_surfaces() returned nothing — mapping is empty"
    drift = []
    for rel, expected in rendered.items():
        target = ROOT / rel
        if not target.exists():
            drift.append(f"{rel}: missing (not generated)")
        elif target.read_text(encoding="utf-8") != expected:
            drift.append(rel)
    assert not drift, (
        "generated surfaces drifted from agent_config/ — regenerate with "
        "`python scripts/_gen_instructions.py`:\n" + "\n".join(sorted(drift))
    )


def test_surfaces_carry_no_orphan_files():
    """The generated instruction trees contain no files outside the agent_config/ mapping."""
    rendered = _render()
    generated = {Path(rel) for rel in rendered}  # render keys are already repo-relative
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
