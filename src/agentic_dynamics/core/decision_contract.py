"""The ONE approval-decision contract: parse, read-committed, validate (migration step 2).

Three consumers grew three dialects for the same act — the runner's checkpoint parser, the
runner's tree-reuse parser, and promote.py's substring checks — and NONE of them validated the
bytes the decision actually committed: the runner parsed the WORKING COPY (an uncommitted edit
could authorize), promote.py accepted `date: nonsense` and an approval with no operator at all.
The d5 incident (2026-09-11) is the same defect seen from the operator's side: a bold inline date
on a `Signed` line failed to parse as a date, so a real signature was refused as unsigned.

This module is the single contract those consumers will consume (step 2 of the migration):

* :func:`parse_approval_decision` reads the markdown artefacts operators actually write —
  canonical ``- key: value`` lines, ``SIGNED-BY-OPERATOR:`` lines (a value that embeds the date
  is split into operator + date), and bold/backticked decorations — into one typed record.
* :func:`read_committed` reads the immutable bytes at a commit (``git show <commit>:<rel>``):
  a working-copy edit is invisible, and a path deleted after its commit still reads back at
  that commit. Approval content is a fact about a commit, never about a checkout.
* :func:`validate_decision` binds the decision to the exact act it authorizes (purpose, spec,
  phase, candidate sha, tree) and applies the non-negotiables: a real operator (non-placeholder)
  and a real date. Consumers surface its named failed checks verbatim.

Tier 0 (stdlib only): the runner (runtime), promote.py (scripts), and the approval command all
need it, and ``core`` is the only plane every layer may import.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: The decision's schema id — the one vocabulary the consumers name.
SCHEMA = "approval-decision/v1"

#: The acts an approval can authorize. A design approval never authorizes implementation,
#: a reuse approval never authorizes promotion — the purpose is part of the binding.
PURPOSE_CHECKPOINT = "checkpoint"
PURPOSE_TREE_REUSE = "tree_reuse"
PURPOSES = frozenset({PURPOSE_CHECKPOINT, PURPOSE_TREE_REUSE})

#: Placeholder signatures that never authorize anything (the union of the runner's and the
#: approval command's sets — one list so the two can never disagree again).
PLACEHOLDER_OPERATORS = frozenset(
    {
        "", "operator", "operator-test", "operator_test", "your name", "your-name",
        "your signature", "sign here", "sign-here", "todo", "tbd", "n/a", "na", "xxx", "???",
        "<name>", "placeholder", "name", "test", "aio",
    }
)

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_GIT_TIMEOUT_S = 30

#: field -> the artifact-key aliases that name it (case-insensitive, decorations stripped).
_ALIASES: dict[str, tuple[str, ...]] = {
    "operator": ("operator", "signed-by-operator", "signed_by_operator", "signed by operator"),
    "date": ("date", "signed-date", "signed_date", "signed on", "signed", "signed-at"),
    "candidate_sha": ("candidate", "candidate-sha", "candidate_sha", "sha"),
    "run_id": ("run", "run-id", "run_id"),
    "gate_id": ("gate", "gate-id", "gate_id"),
    "spec": ("spec", "workflow", "workflow-spec"),
    "phase": ("phase",),
    "tree": ("tree", "tree-hash", "tree_hash"),
    "purpose": ("purpose",),
}

_FIELD_BY_KEY: dict[str, str] = {
    alias: field_name for field_name, aliases in _ALIASES.items() for alias in aliases
}


@dataclass(frozen=True)
class ApprovalDecision:
    """One parsed approval — typed, with the raw key/value pairs kept for evidence."""

    schema: str = SCHEMA
    purpose: str = PURPOSE_CHECKPOINT
    operator: str = ""
    date: str = ""
    candidate_sha: str = ""
    run_id: str = ""
    gate_id: str = ""
    spec: str = ""
    phase: str = ""
    tree: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "purpose": self.purpose,
            "operator": self.operator,
            "date": self.date,
            "candidate_sha": self.candidate_sha,
            "run_id": self.run_id,
            "gate_id": self.gate_id,
            "spec": self.spec,
            "phase": self.phase,
            "tree": self.tree,
        }


def _decorated(value: str) -> str:
    """Strip markdown decoration (bold/italic/backticks/quotes) from a value."""
    return value.strip().strip("*`'\"_ ").strip()


def _normalize_key(raw_key: str) -> str:
    """Normalize an artifact key: lowercase, decorations and `#` stripped, spaces collapsed."""
    key = raw_key.strip().strip("*`#_ ").strip().lower()
    return " ".join(key.split())


def parse_approval_decision(text: str) -> ApprovalDecision:
    """Parse an operator approval artifact into the typed decision.

    Tolerant about how operators write, strict about what the fields mean: missing or
    placeholder fields are left empty/marked and fail their check in :func:`validate_decision`
    (no defaulting). Handles the canonical ``- key: value`` list, ``SIGNED-BY-OPERATOR:`` /
    ``DATE:`` lines, bold decorations, and the d5 shape — an operator line whose value embeds
    the date (``SIGNED-BY-OPERATOR: peparhugo (controller) 2026-09-11``) is split into an
    operator and a date rather than refused as unsigned.
    """
    found: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*!> ").strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            # a bare signed line ("Signed 2026-09-11") still contributes its date
            if not found.get("date") and any(tok in stripped.lower() for tok in ("signed", "date")):
                embedded = _ISO_DATE_RE.search(stripped)
                if embedded:
                    found["date"] = embedded.group(0)
            continue
        raw_key, _, raw_value = stripped.partition(":")
        field_name = _FIELD_BY_KEY.get(_normalize_key(raw_key))
        if field_name is None:
            continue
        value = _decorated(raw_value)
        if field_name == "date":
            embedded = _ISO_DATE_RE.search(value)
            value = embedded.group(0) if embedded else value
        elif field_name == "operator" and value:
            embedded = _ISO_DATE_RE.search(value)
            if embedded:
                if not found.get("date"):
                    found["date"] = embedded.group(0)
                value = value.replace(embedded.group(0), "")
            value = _decorated(value).strip(" ,;").strip()
        if value and field_name not in found:
            found[field_name] = value

    return ApprovalDecision(
        purpose=found.get("purpose", PURPOSE_CHECKPOINT),
        operator=found.get("operator", ""),
        date=found.get("date", ""),
        candidate_sha=found.get("candidate_sha", ""),
        run_id=found.get("run_id", ""),
        gate_id=found.get("gate_id", ""),
        spec=found.get("spec", ""),
        phase=found.get("phase", ""),
        tree=found.get("tree", ""),
        raw=dict(found),
    )


def read_committed(wd: Path | str, commit: str, rel_path: str) -> str | None:
    """The bytes of ``rel_path`` AS COMMITTED at ``commit`` — the immutable decision content.

    ``git show <commit>:<rel>`` reads the blob from the object database: a working-copy edit
    to the same path is invisible (the defect this function closes), and a path deleted from
    the checkout after its commit still reads back at that commit. ``None`` when the path is
    absent at the commit, when ``commit`` is empty, or when git cannot resolve either.
    """
    if not commit or not rel_path:
        return None
    try:
        run = subprocess.run(
            ["git", "show", f"{commit}:{rel_path}"],
            cwd=str(wd),
            capture_output=True,
            encoding="utf-8",
            timeout=_GIT_TIMEOUT_S,
        )
    except Exception:  # noqa: BLE001 — an unresolvable read is "no decision", never a crash
        return None
    if run.returncode != 0:
        return None
    return run.stdout


def operator_is_placeholder(operator: str) -> bool:
    """True when the signature is empty, a known placeholder, or an angle-bracket template.

    Mirrors the runner's check (and the approval command's): a single character is not a
    signature, a generic word is not a name, and ``<your signature>`` is a template.
    """
    stripped = (operator or "").strip()
    norm = " ".join(stripped.lower().split())
    return (
        norm in PLACEHOLDER_OPERATORS
        or len(stripped) < 2
        or (stripped.startswith("<") and stripped.endswith(">"))
    )


def date_is_valid(value: str) -> bool:
    """A real date (ISO-8601 or ``YYYY-MM-DD``); empty/unparseable is not a signature date."""
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _sha_matches(expected: str, named: str) -> bool:
    """True when the artifact names ``expected`` (either side may be the abbreviated form)."""
    expected = (expected or "").strip()
    named = (named or "").strip()
    if not expected or not named:
        return False
    return expected.startswith(named) or named.startswith(expected)


def validate_decision(
    decision: ApprovalDecision,
    *,
    purpose: str | None = None,
    spec: str | None = None,
    phase: str | None = None,
    candidate_sha: str | None = None,
    tree: str | None = None,
) -> list[str]:
    """Bind the decision to the act it authorizes; returns the named failed checks.

    An empty list means the decision authorizes the act described by the expectations. Every
    expected value is compared exactly (the candidate sha may be abbreviated on either side);
    a missing or placeholder operator and a missing/invalid date always fail. Consumers render
    the returned names verbatim in their refusal evidence.
    """
    failed: list[str] = []
    # A DECLARED purpose must match; an artifact written before the purpose vocabulary existed
    # carries none (the per-purpose artifact PATHS keep the bindings distinct, and the
    # approval command writes the purpose from step 2 onward).
    if purpose is not None and "purpose" in decision.raw and decision.purpose != purpose:
        failed.append("purpose")
    if spec is not None and decision.spec != spec:
        failed.append("spec")
    if phase is not None and decision.phase != phase:
        failed.append("phase")
    if candidate_sha is not None and not _sha_matches(candidate_sha, decision.candidate_sha):
        failed.append("candidate_sha")
    if tree is not None and decision.tree != tree:
        failed.append("tree")
    if operator_is_placeholder(decision.operator):
        failed.append("operator")
    if not date_is_valid(decision.date):
        failed.append("date")
    return failed
