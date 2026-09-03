"""Scaffold a minimal valid workflow-v1 definition (Wave-3 authoring, a3).

``workflow new <name>`` scaffolds a NEW operational workflow from the minimal-agent
example (``workflows/examples/minimal-agent-workflow.yaml``) into
``workflows/repository/<name>.yaml`` — the smallest workflow that produces and
verifies a candidate: one agent step commits a candidate sha, a test gate is bound
to that candidate, and promotion requires the gate's pass.

The scaffold is a byte-faithful copy of the example with only the identity scalars
replaced (``metadata.name``, ``metadata.revision`` and ``spec.concurrency.group``);
every comment and block-scalar instruction of the example survives verbatim, so the
scaffolded workflow carries the example's structure and its guidance that prompt text
is instruction, never gate evidence. The composed file is validated AS IT IS WRITTEN —
against ``workflow-v1.schema.json`` AND the a1 semantic linter — before anything hits
disk, and the on-disk file is re-linted after the write. A scaffold that would not be
clean refuses loudly and writes nothing.

This is the ``workflow new`` surface's backing logic. Siblings:
``workflows/lint_workflow.py`` (the a1 linter) and ``workflows/plan_workflow.py``
(the plan renderer).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from workflows import lint_workflow as lw

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "workflows" / "repository"
DEFAULT_TEMPLATE = REPO_ROOT / "workflows" / "examples" / "minimal-agent-workflow.yaml"

#: The metadata.name pattern the workflow-v1 schema enforces — a scaffold must be
#: schema-valid by construction, so the name is validated against it before use.
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")

_HEADER = """\
# {name}.yaml
#
# A minimal valid workflow-v1 definition scaffolded by `agentic-dynamics
# workflow new` from workflows/examples/minimal-agent-workflow.yaml — the
# smallest workflow that produces and verifies a candidate.
#
# Shape: one agent step (implement) commits a candidate sha, a test gate (verify)
# is bound to that candidate, and promotion requires the gate's pass.
#
# The intended first edit is the implement step's prompt. The scaffold validates
# against workflows/schema/workflow-v1.schema.json and passes the workflow linter
# as written. Operational status is never authored here — completion follows the
# revision.
"""

#: The document's identity scalars a scaffold rewrites. Each must appear exactly once
#: as a ``key: <value>`` line in the template body — a drift (zero or many matches)
#: fails the scaffold rather than producing a subtly wrong copy.
_SCALAR_KEYS = ("name", "revision", "group")


class ScaffoldError(Exception):
    """A scaffold could not be produced: the name, template, or validation refused."""


def valid_name(name: str) -> bool:
    """True when ``name`` is a legal workflow slug (the schema's metadata.name pattern)."""
    return bool(NAME_PATTERN.match(name))


def default_output_dir(root: Path | None = None) -> Path:
    """The default scaffold target directory: ``workflows/repository/`` under ``root``."""
    root = Path(root) if root is not None else REPO_ROOT
    return root / "workflows" / "repository"


def scaffold(
    name: str,
    *,
    output_dir: str | Path | None = None,
    template_path: str | Path | None = None,
    root: Path | None = None,
) -> Path:
    """Scaffold ``workflows/repository/<name>.yaml`` from the minimal-agent example.

    The scaffolded file is validated against the schema AND the a1 linter as it is
    written — a template that would not produce a clean workflow refuses and writes
    nothing. Returns the written path.
    """
    root = Path(root) if root is not None else REPO_ROOT
    if not valid_name(name):
        raise ScaffoldError(
            f"invalid workflow name {name!r}: must match {NAME_PATTERN.pattern!r} "
            "(lowercase letter, then lowercase/digits/underscore/hyphen)"
        )

    template = Path(template_path) if template_path is not None else DEFAULT_TEMPLATE
    if not template.is_file():
        raise ScaffoldError(f"scaffold template not found: {template}")

    target = (Path(output_dir) if output_dir is not None else default_output_dir(root)) / f"{name}.yaml"
    if target.exists():
        raise ScaffoldError(f"refusing to overwrite existing workflow: {target}")

    template_text = template.read_text(encoding="utf-8")
    body = _body_of(template_text)
    document = _load_workflow_v1(body, template)
    old_name = _identity_value(document, "metadata", "name", template)
    old_group = _identity_value(document, ("spec", "concurrency"), "group", template)

    body_edited = _replace_scalar(body, "name", old_name, name)
    body_edited = _replace_scalar(body_edited, "group", old_group, name)
    body_edited = _replace_scalar(body_edited, "revision", _revision_of(document), "1")

    composed = _HEADER.format(name=name) + body_edited
    _require_clean(composed, template, name)
    _require_identity(composed, name)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(composed, encoding="utf-8")
    try:
        on_disk = lw.lint_path(target)
    except Exception as exc:  # pragma: no cover — defensive: composed text already passed
        target.unlink(missing_ok=True)
        raise ScaffoldError(f"scaffold failed on-disk validation: {exc}") from exc
    if not on_disk.ok:
        target.unlink(missing_ok=True)
        codes = ", ".join(on_disk.codes)
        raise ScaffoldError(f"scaffold failed on-disk validation ({codes}) — nothing written")
    return target


# --------------------------------------------------------------------------- #
# Template handling
# --------------------------------------------------------------------------- #
def _body_of(text: str) -> str:
    """The document body — everything from the ``apiVersion:`` line onward."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.lstrip().startswith("apiVersion:"):
            return "".join(lines[index:])
    raise ScaffoldError("template is not a workflow-v1 definition (no apiVersion line)")


def _load_workflow_v1(body: str, template: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise ScaffoldError(f"template is not valid YAML: {exc}") from exc
    if not lw.is_workflow_v1_document(document):
        raise ScaffoldError(f"template {template} is not a workflow-v1 definition")
    return document


def _identity_value(document: dict[str, Any], keys: str | tuple[str, ...], key: str, template: Path) -> str:
    if isinstance(keys, str):
        keys = (keys,)
    node: Any = document
    for part in keys:
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            break
    value = node.get(key) if isinstance(node, dict) else None
    if not isinstance(value, str) or not value:
        raise ScaffoldError(f"template {template} carries no {'.'.join(keys)}.{key} to scaffold")
    return value


def _revision_of(document: dict[str, Any]) -> str:
    metadata = document.get("metadata")
    revision = metadata.get("revision") if isinstance(metadata, dict) else None
    if not isinstance(revision, str) or not revision:
        return "1"
    return revision


def _replace_scalar(text: str, key: str, old: str, new: str) -> str:
    """Replace the single ``key: <old>`` scalar value with ``<new>``.

    The value is matched by PARSED equality, not raw text, so a quoted scalar in the
    template (``revision: "1"``) is found and rewritten to a properly re-quoted
    replacement (yaml.safe_dump keeps ``revision`` a string, never a number). A name
    can never be rewritten as a substring of a comment or a block-scalar instruction —
    only the key's own value changes.
    """
    matches = []
    for match in re.finditer(
        rf"^(\s*{re.escape(key)}:)([ \t]*)(.*)$", text, re.MULTILINE
    ):
        rest = match.group(3).strip()
        if not rest or rest in (">-", "|", ">-", "|-"):
            continue  # a block-scalar indicator, not an inline value
        try:
            parsed = yaml.safe_load(rest)
        except yaml.YAMLError:
            continue
        if parsed == old:
            matches.append(match)
    if len(matches) != 1:
        raise ScaffoldError(
            f"scaffold template drifted: expected exactly one {key}: {old} scalar, "
            f"found {len(matches)} — refusing a partial copy"
        )
    match = matches[0]
    return text[: match.start(3)] + _yaml_scalar(new) + text[match.end(3):]


def _yaml_scalar(value: str) -> str:
    """Render a scalar the way a hand author would: plain when it round-trips as a
    string, single-quoted otherwise (``"1"`` must stay a string, never a number)."""
    try:
        if yaml.safe_load(value) == value:
            return value
    except yaml.YAMLError:  # pragma: no cover — a plain scalar cannot raise
        pass
    return "'" + value.replace("'", "''") + "'"


def _require_clean(composed: str, template: Path, name: str) -> None:
    report = lw.lint_text(composed)
    if report.ok:
        return
    codes = ", ".join(sorted(report.codes))
    raise ScaffoldError(
        f"scaffold of {name!r} from {template} is not linter-clean ({codes}) — "
        "a new workflow must be schema-valid and linter-clean as written; nothing written"
    )


def _require_identity(composed: str, name: str) -> None:
    document = yaml.safe_load(composed)
    metadata = document.get("metadata") if isinstance(document, dict) else None
    spec = document.get("spec") if isinstance(document, dict) else None
    concurrency = spec.get("concurrency") if isinstance(spec, dict) else None
    if not isinstance(metadata, dict) or metadata.get("name") != name:
        raise ScaffoldError("scaffold failed to set metadata.name — nothing written")
    if not isinstance(concurrency, dict) or concurrency.get("group") != name:
        raise ScaffoldError("scaffold failed to set spec.concurrency.group — nothing written")
