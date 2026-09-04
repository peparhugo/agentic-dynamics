"""Producer-side wave-verdict record derivation for the self-knowledge layer (loop 2).

The wave-verdict record is phase ``s3a_wave_verdict_type``'s substrate (``self_knowledge_layer``
wave, design ``docs/designs/proposed/self_knowledge_layer.md``): at run completion the run
emits ONE narrative record — the "what happened and why" the AIO currently re-derives by grep
(prereg Edge 3). This module is the record TYPE both the future emission hook (s3b) and the s5
scoreboard ride on; it derives a ``source_type=wave_verdict`` KnowledgeRecord from the three
artifacts that already exist when a spec run completes:

* the **run ledger** (``experiments/results/workflows/<spec>/<timestamp>.json`` — the terminal
  run disposition, the measured cost, and the phase list);
* the **control-db row** (the ``runs`` table row for this ``run_id`` — the authoritative
  merge/permanence state: ``promotable`` / ``merged`` / ``published`` / ``failed`` / ...);
* the **adversarial review artifact** (``docs/reviews/<spec>_adversarial.md`` — OPTIONAL; when
  present it contributes the finding count and the residual list).

The record's content fields are the deliverable's fixed shape::

    {spec_name, run_id, verdict, cost, phases_total,
     adversarial_findings_count (present ONLY when a review doc exists), merge_state,
     residuals []}

plus the one-paragraph ``narrative`` ("what happened and why") and the context-abstraction
dimensions (``actor`` + ``scope``). Verdict vocabulary is the corpus's existing wave-verdict
vocabulary (``merge-ready`` / ``clean`` / ``not`` — the same words ``kb_backfill_findings.py``
minted for the k2 wave-conclusion records), so the belief layer (s4) and the scoreboard (s5)
can treat every wave verdict uniformly.

Actor + scope follow the design's actor-layering table: the producer is **the run** and the
record lives in the run's OWN workload/job scope (``workload:<spec>/job:<cell>`` — not the AIO's
org root). Structurally the record keeps the org id as ``repository_id`` (the same corpus
anchoring session/decision records use, so an org-root reader resolves it and the retrieval hard
pre-filter excludes every ``self-*`` / foreign cell scope), while ``acl_scope`` and the payload
``scope`` key name the run's own job — self-describing so a consumer sees at a glance where the
record lives and that it is not an AIO-private record. The ``actor`` key travels in the payload
(the KB schema has no actor field — the sibling producers' convention).

Identity: one verdict per run. ``logical_locator`` is the ``run_id`` and ``source_uri`` is
``wave_verdict:<run_id>`` — a family distinct from ``session:<slug>`` / ``decision:<id>`` /
``wave:<name>`` (the k2 backfill's). ``entity_id`` is therefore stable across re-derivations of
the SAME run (a re-derive after the run's merge state advanced re-keys ``knowledge_id`` while
``entity_id`` holds — exactly the version-chain a scoreboard needs), and the run's own
``git_sha``/``candidate_sha`` is the source_revision folded into ``knowledge_id`` (the record is
bound to the candidate the verdict judges, so two different candidates never collide).

The verdict/``merge_state`` are deterministic functions of the inputs (no LLM): the review doc's
signals when a review doc exists (falling back to the run's own terminal disposition), and the
control-db row's ``state`` read verbatim as ``merge_state`` (falling back to a local
ledger-state mirror of ``control_db.run_state_from_ledger_state`` when no control row is
supplied). Determinism is what makes the record rerun-safe: identical inputs yield identical
bytes and therefore identical ids.

Scope fence: the TYPE ONLY — derivation + record construction. The run-completion EMISSION hook
is s3b (a separate phase); nothing here writes to the KB or registers a command.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from agentic_dynamics.knowledge.knowledge import (
    Authority,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
from agentic_dynamics.knowledge.record_factory import build_record as build_record_from_parts

# ── Extractor contract constants ────────────────────────────────

#: ``source_type`` recorded on every wave-verdict record — registered in
#: ``knowledge.SOURCE_TYPES`` as an observation-family DERIVED/``[C]`` row (a verdict states what
#: a run's completion was, never an instruction to act; it is a deterministic synthesis over
#: measured ledger/control state + the advisory review, so DERIVED is the honest nominal — it can
#: feed the scoreboard but never masquerade as an independent measurement).
SOURCE_TYPE = "wave_verdict"

#: The extractor generation. ``knowledge_id`` folds this in, so the wave-verdict family is
#: identity-distinct from every sibling producer (session/``meta_session``, ``decision``,
#: ``observation``, the k2 ``finding`` wave records) even for byte-identical bodies. A literal —
#: stability is the point.
EXTRACTOR_VERSION = "wave-verdict/v1"

#: The producer/actor of every wave-verdict record. The RUN emits the record at its own
#: completion; the value travels in the payload (self-describing — the KB schema has no ``actor``
#: field).
ACTOR = "run"

#: Fallback ``source_revision`` when the run carries no git sha to bind to. Mirrors the sibling
#: producers' fallback convention; in practice a completed run always has one (the ledger
#: ``git_sha`` / the control row ``candidate_sha``).
REVISION_FALLBACK = "wave-verdict/unrevisioned"

#: The content fields the deliverable fixes (plus ``narrative``/``actor``/``scope``). The list is
#: documentation — the derivation below builds exactly these keys — so a reader can see at a
#: glance what a wave verdict carries.
CONTENT_FIELDS = (
    "spec_name",
    "run_id",
    "verdict",
    "cost",
    "phases_total",
    "adversarial_findings_count",
    "merge_state",
    "residuals",
    "narrative",
)

#: The wave-verdict vocabulary — the corpus's existing wave verdict words (kb_finding_layer's k2
#: backfill minted ``VERDICTS = ("merge-ready", "not", "clean")``; kept identical so the s4 belief
#: layer and the s5 scoreboard treat every wave verdict uniformly, whether it was backfilled or
#: emitted live at run completion).
VERDICTS = ("merge-ready", "not", "clean")

#: The control-db run states that count as "the run reached a green terminal outcome" when a
#: review doc is absent (the verdict fallback). Mirrors the positive half of the control
#: vocabulary — a run sitting in any of these produced a mergeable candidate.
_GREEN_CONTROL_STATES = frozenset(
    {"promotable", "promoting", "merged", "projecting", "published"}
)


# ── Job-scope helpers (the run's own workload/job scope) ────────


def job_cell_id(spec_name: str, model: str) -> str:
    """Return the workflow-job cell id a spec run lives in: ``wf_<spec>_<model>``.

    Mirrors ``workflow_runner._cell_id`` / the reducers' ``cell_id`` verbatim (re-declared here
    rather than imported so a knowledge producer stays import-light — the same rationale
    ``control/reducers/_common.py:44`` documents for the reducers' own re-declaration). The run
    ledger's attempts already carry this as their ``job_id``, so it is the run's own job cell in
    the control plane, not an invented key.
    """
    slug = "".join(ch if ch.isalnum() else "_" for ch in f"{spec_name}_{model}")
    return f"wf_{slug.lower().strip('_')}"


def wave_verdict_acl_scope(spec_name: str, model: str = "") -> str:
    """Return the run's own scope a wave verdict lives in: ``workload:<spec>/job:<cell>``.

    The design's actor-layering table names this scope verbatim ("the run | workload:<spec>/
    job:<cell> (its own)"). ``acl_scope`` carries it (distinct from the corpus's ``"public"``
    rows and from an AIO ``org:<repo>`` scope) and the payload ``scope`` key mirrors it, so the
    record is self-describing: a reader sees it is the run's own job record, never an
    AIO-private org-root record.
    """
    return f"workload:{spec_name}/job:{job_cell_id(spec_name, model)}"


# ── Deterministic review-artifact parsing (no LLM) ──────────────


def _verdict_signals(text: str) -> dict[str, bool]:
    """Boolean signal map over a review doc's lowercased text.

    Deliberately coarse and independent (the same posture ``kb_backfill_findings._verdict_signals``
    documents): the classifier combines them in a fixed precedence so a doc that says both "PASS"
    and "merge-blocked" resolves honestly (a merge-block outranks a positive re-verification).
    """
    t = text.lower()
    return {
        "merge_ready": bool(re.search(r"merge[- ]?ready", t)),
        "not_merge_ready": bool(re.search(r"not merge[- ]?ready|merge[- ]?blocked", t)),
        "verdict_fail": bool(re.search(r"\bverdict:?\s*fail\b|release verdict[^\n]*fail", t)),
        "verdict_pass": bool(re.search(r"\bverdict:?\s*pass\b|release verdict[^\n]*pass", t)),
        "passfail_fail": bool(re.search(r"pass\s*/\s*fail[^\n]*:\s*fail", t)),
        "passfail_pass": bool(re.search(r"pass\s*/\s*fail[^\n]*:\s*pass", t)),
        "no_failed_finding": bool(re.search(r"no failed finding|0 findings?|no findings?", t)),
        "clean_sweep": bool(re.search(r"clean sweep|failed to falsify|not falsified", t)),
        "blocker": bool(re.search(r"merge[- ]?blocker|blocking the merge|blocked on", t)),
    }


def _verdict_statement(text: str) -> str:
    """The review doc's OWN verdict statement, bounded to one sentence, else the whole text.

    Adversarial reviews open with a bolded self-verdict (``**Verdict: PASS (merge-ready).**``,
    ``**VERDICT: FAIL — ...**``, ``**Release verdict: merge-ready to main.**``,
    ``**Overall adversarial verdict: FAILED to falsify.**``) and then QUOTE other waves'
    evidence below it — including other waves' "Verdict: FAIL" lines. A whole-text scan therefore
    lets a quoted FAIL override the doc's own PASS, which mis-verdicts the doc. The classifier
    must first read the doc's own statement: the FIRST bold verdict marker in document order,
    captured to the end of its sentence (the ``kb_backfill_findings._bounded_lead`` convention).
    Returns the whole text when the doc carries no bold verdict marker (the no-marker review
    shape, where the whole-text scan is the only signal).
    """
    marker = re.compile(
        r"\*\*\s*(?:VERDICT|Verdict|Release verdict|Overall adversarial verdict)\s*:",
        re.IGNORECASE,
    )
    m = marker.search(text)
    if not m:
        return text
    boundary = re.search(r"[.!?](?:\s|$)", text[m.start() :])
    cut = m.start() + (boundary.end() if boundary else min(len(text) - m.start(), 480))
    return text[m.start() : cut]


def classify_wave_verdict(
    review_text: str, *, run_succeeded: bool, control_state: str | None = None
) -> str:
    """Deterministic wave-verdict classifier -> one of ``merge-ready`` / ``not`` / ``clean``.

    Fixed precedence (documented in the module docstring, mirroring the corpus's existing wave
    verdict vocabulary):

      1. the review doc's OWN verdict statement (its bold ``**Verdict:`` marker — see
         :func:`_verdict_statement`) is classified first, so quoted evidence from OTHER waves
         can never override this doc's own PASS/FAIL;
      2. a merge-block / not-merge-ready / FAIL verdict / PASS-FAIL-fail / blocker signal
         -> ``not`` (a merge-block outranks a positive re-verification);
      3. a merge-ready signal -> ``merge-ready``;
      4. a PASS / PASS-FAIL-pass / clean-sweep / no-failed-finding signal -> ``clean``;
      5. with NO review doc, the run's own terminal disposition decides: a green control state
         (``promotable``/``merged``/...) or a successful ledger -> ``clean``, anything else
         -> ``not`` (a failed/cancelled/awaiting run is a negative verdict, never silence).

    ``run_succeeded`` is the ledger's own ``ok``/``state`` reading (True for ``succeeded``);
    ``control_state`` is the control row's state when one exists. The green fallback NEVER
    fabricates ``merge-ready`` — a run without a review doc can read ``clean`` at most.
    """
    if review_text and review_text.strip():
        signals = _verdict_signals(_verdict_statement(review_text))
        if (
            signals["not_merge_ready"]
            or signals["verdict_fail"]
            or signals["passfail_fail"]
            or signals["blocker"]
        ):
            return "not"
        if signals["merge_ready"] and not signals["verdict_fail"]:
            return "merge-ready"
        if signals["verdict_pass"] or signals["passfail_pass"] or signals["clean_sweep"]:
            return "clean"
        if signals["no_failed_finding"]:
            return "clean"
        # A review doc with no usable signal falls through to the run disposition.
    if run_succeeded or control_state in _GREEN_CONTROL_STATES:
        return "clean"
    return "not"


def _review_findings_count(text: str) -> int:
    """Deterministic finding-count extraction from an adversarial review doc.

    Mirrors ``kb_backfill_findings.finding_count``'s conventions: an explicit
    ``Findings: N`` / ``N findings`` line wins; otherwise the number of finding-table rows whose
    first cell is a ``F#``/``A#``/``R#``/``G#`` marker (wide or heading shapes); else 0 (a
    clean-sweep doc genuinely records none).
    """
    m = re.search(r"findings?:?\s*(\d+)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    table_rows = re.findall(
        r"^\s*\|\s*\*?\*?[A-Za-z]-?A?\d+\s*\*?\*?\|", text, re.MULTILINE
    )
    if table_rows:
        return len(table_rows)
    heading_rows = re.findall(r"^#{2,4}\s+F-?A?\d+\b", text, re.MULTILINE)
    return len(heading_rows)


def _review_residuals(text: str, *, limit: int = 6) -> list[str]:
    """Deterministic residual extraction from an adversarial review doc.

    Captures finding-table disposition cells that name a limitation ("RECORD", "accepted
    limitation", "residual", "not fixed") plus ``Accepted limitations`` / ``Residual`` bullets,
    deduplicated and bounded so the record text stays a retrieval surface rather than a
    transcript dump. Table header cells (column labels) are never residuals.
    """
    residuals: list[str] = []
    header_labels = {
        "fix-or-record", "residual scope", "residual", "fix or record", "disposition",
        "severity", "finding", "attack", "re-verification", "evidence", "result", "#",
        "fix / record", "fix-or-record (decision)", "re-verification evidence",
    }
    # Finding-table rows with a disposition cell (>= 4 pipe-separated cells, so the header row
    # `| # | Attack |` never qualifies).
    for row in re.findall(
        r"^\s*\|[^\n]*\|[^\n]*\|[^\n]*\|[^\n]*$", text, re.MULTILINE
    ):
        cells = [c.strip() for c in row.strip("|").split("|")]
        for cell in cells:
            label = cell.lower().strip("*_ `")
            if label in header_labels or len(label) <= 8:
                continue
            low = cell.lower()
            if any(
                k in low
                for k in ("accepted limitation", "record", "residual", "not fixed", "limitation")
            ):
                residuals.append(re.sub(r"\s+", " ", cell)[:220])
    for section in re.findall(
        r"^#{2,4}\s*(?:accepted limitations?|residual[^\n]*)[^\n]*\n(.*?)(?=^#{1,4}|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    ):
        for line in section.splitlines():
            s = line.strip().lstrip("*-–—>")
            if s and len(s) > 12 and not s.startswith("|"):
                residuals.append(re.sub(r"\s+", " ", s)[:220])
    seen: set[str] = set()
    out: list[str] = []
    for item in residuals:
        key = item[:80]
        if key not in seen:
            seen.add(key)
            out.append(item)
        if len(out) >= limit:
            break
    return out


# ── Small deterministic helpers ─────────────────────────────────


def _required(ledger: dict[str, Any], control_row: dict[str, Any] | None, field: str) -> str:
    """Return a required identifier field, preferring the ledger, from either input.

    ``spec_name``/``run_id`` must exist for a stable record; the ledger carries them and the
    control row repeats them, so either source satisfies the requirement (the ledger wins when
    both present — it is the run's own account).
    """
    value = str(ledger.get(field) or (control_row or {}).get(field) or "").strip()
    if not value:
        raise ValueError(f"run has no {field!r} — cannot derive a wave-verdict record")
    return value


def _model(ledger: dict[str, Any], control_row: dict[str, Any] | None) -> str:
    """The run's model (ledger preferred), for the job-cell derivation."""
    return str(ledger.get("model") or (control_row or {}).get("model") or "").strip()


def _finite_cost(ledger: dict[str, Any], control_row: dict[str, Any] | None) -> float:
    """The measured run cost in USD: the ledger's ``total_cost_usd``, else the row's ``cost_usd``.

    Measured-or-absent, never a fabricated zero on a missing value: if neither input carries a
    number the record must not mint a 0.0 cost that would poison the scoreboard's per-wave
    average. Raises ``ValueError`` when no measured cost exists.
    """
    for source in (ledger, control_row or {}):
        value = source.get("total_cost_usd", source.get("cost_usd"))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    raise ValueError("run carries no measured cost (total_cost_usd/cost_usd) — cannot derive a "
                     "wave-verdict record")


def _phases_total(ledger: dict[str, Any]) -> int:
    """The run's phase total: the recorded phase list's length, else the attempt count.

    The ledger's ``phases`` array is the run's own per-phase log (including test-gate phases); the
    ``attempt_count`` is the fallback for ledgers that predate the array.
    """
    phases = ledger.get("phases")
    if isinstance(phases, (list, tuple)) and phases:
        return len(phases)
    attempts = ledger.get("attempt_count")
    if isinstance(attempts, int) and not isinstance(attempts, bool):
        return attempts
    return 0


def _ledger_run_succeeded(ledger: dict[str, Any]) -> bool:
    """The run's own green reading: ``ok`` True, or a terminal ``succeeded`` state."""
    ok = ledger.get("ok")
    if isinstance(ok, bool):
        return ok
    return str(ledger.get("state") or "").strip() == "succeeded"


def _merge_state(
    ledger: dict[str, Any], control_row: dict[str, Any] | None
) -> str:
    """The run's merge/permanence state, read from the control-db row verbatim.

    The control row's ``state`` IS the control plane's measured answer to "where does this run
    stand relative to the merge?" (``promotable`` / ``merged`` / ``published`` / ``failed`` /
    ``cancelled`` / ...). When no control row is supplied, a local mirror of
    ``control_db.run_state_from_ledger_state`` derives the same vocabulary from the ledger's own
    terminal label (``succeeded`` -> ``promotable`` — phases passing authorises a promotion, it
    does not ARE one — ``failed`` -> ``failed``, ``cancelled`` -> ``cancelled``,
    ``awaiting_approval`` -> ``awaiting_approval``).
    """
    control_state = str((control_row or {}).get("state") or "").strip()
    if control_state:
        return control_state
    ledger_state = str(ledger.get("state") or "").strip()
    mirror = {
        "succeeded": "promotable",
        "awaiting_approval": "awaiting_approval",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    return mirror.get(ledger_state, "")


# ── The canonical content payload ───────────────────────────────


def wave_verdict_payload(
    ledger: dict[str, Any],
    control_row: dict[str, Any] | None = None,
    review_text: str | None = None,
) -> dict[str, Any]:
    """Return the canonical content payload for ONE wave-verdict record.

    The deliverable's fixed shape — ``spec_name``, ``run_id``, ``verdict``, ``cost``,
    ``phases_total``, ``merge_state``, ``residuals``, and ``adversarial_findings_count`` which is
    present ONLY when a review doc exists — plus the one-paragraph ``narrative`` and the
    record's ``actor``/``scope`` dimensions. ``scope`` mirrors the record's own ``acl_scope``
    (``wave_verdict_acl_scope``); ``actor`` is the module's ``ACTOR`` literal (the run).

    ``review_text`` is the adversarial review artifact's text when one exists (``None`` = no
    review doc). When present, ``verdict`` is classified from its signals, ``residuals`` lists
    its recorded limitations, and ``adversarial_findings_count`` is its finding count; when
    absent all three fall back to the run's own disposition (clean/not) + empty residuals, and
    the findings-count key is OMITTED (a clean-sweep run without a review doc must not read as a
    review that recorded zero findings). This dict is what ``text`` serializes (sorted keys), so
    it is the entire hashed body: two derivations of the same inputs yield byte-identical bodies
    and therefore identical ids (rerun-safe), while a changed merge state or a new review doc
    yields a new body and a new ``knowledge_id`` for the same run.
    """
    spec_name = _required(ledger, control_row, "spec_name")
    run_id = _required(ledger, control_row, "run_id")
    model = _model(ledger, control_row)
    control_state = str((control_row or {}).get("state") or "").strip() or None

    run_succeeded = _ledger_run_succeeded(ledger)
    review_present = bool(review_text and review_text.strip())
    verdict = classify_wave_verdict(
        review_text or "", run_succeeded=run_succeeded, control_state=control_state
    )

    cost = _finite_cost(ledger, control_row)
    merge_state = _merge_state(ledger, control_row)
    phases_total = _phases_total(ledger)
    residuals = _review_residuals(review_text) if review_present else []
    findings_count = _review_findings_count(review_text) if review_present else None
    narrative = _render_narrative(
        spec_name, run_id, verdict, cost, phases_total, merge_state, findings_count, residuals
    )
    payload: dict[str, Any] = {
        "spec_name": spec_name,
        "run_id": run_id,
        "verdict": verdict,
        "cost": round(cost, 6),
        "phases_total": phases_total,
        "merge_state": merge_state,
        "residuals": residuals,
        "narrative": narrative,
        "actor": ACTOR,
        "scope": wave_verdict_acl_scope(spec_name, model),
    }
    if findings_count is not None:
        payload["adversarial_findings_count"] = findings_count
    return payload


def _render_narrative(
    spec_name: str,
    run_id: str,
    verdict: str,
    cost: float,
    phases_total: int,
    merge_state: str,
    findings_count: int | None,
    residuals: list[str],
) -> str:
    """The one-paragraph "what happened and why", rendered deterministically from the inputs.

    Never a free-text LLM summary — a stable, bounded paragraph assembled from the measured
    fields the verdict records, so identical inputs always yield identical narrative bytes. This
    is the paragraph the AIO reads instead of re-deriving the wave's outcome by grep.
    """
    review_clause = (
        f"the adversarial review recorded {findings_count} finding(s)"
        if findings_count is not None
        else "no adversarial review artifact accompanied this run"
    )
    residual_clause = (
        f" and left {len(residuals)} residual(s) on record" if residuals else ""
    )
    return (
        f"Wave {spec_name} ({run_id}) came to a {verdict} verdict after {phases_total} phases "
        f"at ${cost:.4f}; its merge/permanence state is {merge_state or 'unrecorded'}, "
        f"{review_clause}{residual_clause}. This narrative is derived from the run ledger, its "
        "control-db row, and the adversarial review artifact, never re-derived by grep."
    )


# ── Record construction ─────────────────────────────────────────


def build_wave_verdict_record(
    ledger: dict[str, Any],
    control_row: dict[str, Any] | None = None,
    review_text: str | None = None,
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=wave_verdict`` record from a run ledger + control row + review.

    ``ledger`` is the run ledger (``spec_name``/``run_id``/``model``/``total_cost_usd``/
    ``phases``/``ok`` or ``state``); ``control_row`` is the ``runs`` table row (``state``,
    ``cost_usd``, ``candidate_sha``) or ``None``; ``review_text`` is the adversarial review
    artifact's text or ``None``. The record's ``text`` is the canonical JSON body from
    :func:`wave_verdict_payload` — deterministic, so ``content_hash``/``knowledge_id`` are
    rerun-safe for identical inputs.

    Identity follows the canonical contract in :mod:`knowledge`:

    * ``logical_locator`` is the ``run_id``; ``source_uri`` is ``wave_verdict:<run_id>`` — a
      family distinct from the k2 backfill's ``wave:<name>`` finding records and from every
      sibling producer, so the wave verdict never collides on ``entity_id``.
    * ``revision`` is the run's own git sha (the control row ``candidate_sha``, else the ledger
      ``git_sha``) when one exists — the record is bound to the candidate the verdict judges —
      else :data:`REVISION_FALLBACK`.
    * ``entity_id = sha256(repository_id | source_uri | logical_locator)``; ``content_hash`` is
      the sha256 of the durable artifact; ``knowledge_id`` folds them with the revision + the
      ``wave-verdict/v1`` extractor. Re-deriving the SAME run with identical inputs is a no-op; a
      re-derivation after the run's merge state advanced re-keys ``knowledge_id`` while
      ``entity_id`` holds (a new version of the same run slot).

    ``authority`` is ``DERIVED`` / ``[C]`` — the registered nominal for ``wave_verdict``: the
    record is a deterministic synthesis over the measured ledger/control state + the advisory
    review doc, so it can feed the scoreboard and the belief layer but never masquerade as an
    independent measurement. ``repository_id`` defaults to the org id and ``acl_scope`` to the
    run's own workload/job scope (see :func:`wave_verdict_acl_scope`). ``observed_at`` is the
    run's own completion instant (the real "when this verdict happened") while
    ``valid_from``/``indexed_at`` stay the derivation/consumer clocks.

    Raises ``ValueError`` when the run carries no ``spec_name``/``run_id`` or no measured cost.
    """
    payload = wave_verdict_payload(ledger, control_row=control_row, review_text=review_text)
    run_id = payload["run_id"]
    scope = payload["scope"]

    candidate = str((control_row or {}).get("candidate_sha") or "").strip()
    git_sha = str(ledger.get("git_sha") or "").strip()
    revision = candidate or git_sha or REVISION_FALLBACK
    commit_sha = revision if (candidate or git_sha) else ""

    observed_at = (
        str(ledger.get("ended_at") or (control_row or {}).get("ended_at") or "").strip()
    )

    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=f"wave_verdict:{run_id}",
        logical_locator=run_id,
        repository_id=repository_id,
        revision=revision,
        authority=Authority.DERIVED,
        evidence_class="[C]",
        text=json.dumps(payload, sort_keys=True),
        extra_fields={
            "commit_sha": commit_sha,
            "extractor_version": EXTRACTOR_VERSION,
            "acl_scope": scope,
            "observed_at": observed_at,
            "outcome_id": payload["spec_name"],
        },
        now=now,
    )


def derive_wave_verdict(
    ledger: dict[str, Any],
    control_row: dict[str, Any] | None = None,
    review_text: str | None = None,
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public derivation entry point — delegates to :func:`build_wave_verdict_record`.

    Deliberately singular (like the session/decision producers): one completed run always yields
    exactly one wave-verdict record, with no batch pre-filter case. A run missing its
    ``spec_name``/``run_id``/cost is a genuine caller error, not a skip case.
    """
    return build_wave_verdict_record(
        ledger,
        control_row=control_row,
        review_text=review_text,
        repository_id=repository_id,
        now=now,
    )
