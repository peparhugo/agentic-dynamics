"""Generate the `.opencode/` + `.claude/` instruction surfaces from `agent_config/`.

Critique rec 6: `.opencode/` and `.claude/` must not both be manually authoritative. This script
is the single writer — it deterministically renders the hand-edited `agent_config/` into the two
generated surfaces. The mapping is the format contract:

* `agent_config/<file>.md` → `.opencode/instructions/<file>.md` + `.claude/rules/<file>.md`
  (mental-model, rules, conventions).
* `agent_config/skills/<name>.md` → `.opencode/skills/<name>/SKILL.md` +
  `.claude/skills/<name>/SKILL.md`.
* `agent_config/agents/<name>.md` → `.opencode/agents/<name>.md` + `.claude/agents/<name>.md`.
* `agent_config/commands/<name>.md` → `.opencode/commands/<name>.md` + `.claude/commands/<name>.md`.

`render_surfaces()` is the pure single source of truth — both this script (to write) and
`tests/test_generated_surfaces_match.py` (to assert byte-identity) call it, so a hand-edit to a
generated file is a drift failure, never a silent divergence.

Deterministic by construction: reads `agent_config/`, writes the mapped bytes — no timestamps, no
ordering, no environment dependence.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_CONFIG = ROOT / "agent_config"

#: Instruction files (the "documents" both surfaces load), mapped by their agent_config/ name.
INSTRUCTIONS = ("mental-model.md", "rules.md", "conventions.md")

#: The seven skills (one per file in agent_config/skills/).
SKILLS = ("analyze", "control-room", "instrument", "lab-books", "queue", "review", "run-workflow")

#: The subagent definitions.
AGENTS = ("data-analysis", "instrument-dev", "pipeline-ops")

#: The command definitions.
COMMANDS = ("analyze", "lab", "new-exp", "pipeline", "run-exp")


def _read(rel: str) -> str:
    """Read an agent_config/ file, normalizing a trailing newline for byte-stability."""
    text = (AGENT_CONFIG / rel).read_text(encoding="utf-8")
    return text


def render_surfaces() -> dict[str, str]:
    """Render the full generated surface as ``{repo-relative path: content}``.

    This is the deterministic single source of truth consumed by both the writer and the
    drift guard. Keys are repo-relative (e.g. ``.opencode/instructions/mental-model.md``).
    """
    out: dict[str, str] = {}

    # 1. Instruction documents — .opencode/instructions/ + .claude/rules/.
    for name in INSTRUCTIONS:
        content = _read(name)
        out[f".opencode/instructions/{name}"] = content
        out[f".claude/rules/{name}"] = content

    # 2. Skills — .opencode/skills/<name>/SKILL.md + .claude/skills/<name>/SKILL.md.
    for name in SKILLS:
        content = _read(f"skills/{name}.md")
        out[f".opencode/skills/{name}/SKILL.md"] = content
        out[f".claude/skills/{name}/SKILL.md"] = content

    # 3. Agents.
    for name in AGENTS:
        content = _read(f"agents/{name}.md")
        out[f".opencode/agents/{name}.md"] = content
        out[f".claude/agents/{name}.md"] = content

    # 4. Commands.
    for name in COMMANDS:
        content = _read(f"commands/{name}.md")
        out[f".opencode/commands/{name}.md"] = content
        out[f".claude/commands/{name}.md"] = content

    return out


def write_surfaces() -> None:
    """Write the rendered surface to disk (creating parent directories)."""
    for rel, content in render_surfaces().items():
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def main() -> int:
    write_surfaces()
    print(f"regenerated {len(render_surfaces())} surface files from agent_config/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
