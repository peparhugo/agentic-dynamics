"""DockerAgentExecutor — the P0-2 sibling-container step executor (composition root side).

Implements ``runtime.executor.StepExecutor``: run ONE agent phase inside a sibling
container (scope-driven mounts/network/env, validated by the spawn wrapper BEFORE any
socket call) and return a structured :class:`StepResult`. This is the executor the
``--orchestrator`` flag injects into the ONE workflow engine — it never reimplements
the phase loop, stop-on-failure, checkpoints, gates, or the ledger; the engine owns
all of those (P0-2, control-plane stabilization).

The child runs ``run_workflow.py --only-phase <name>`` inside the container — the
normal single-phase path, with the P0-1 exit-code contract + result envelope. The
executor classifies the child by its envelope first (``ok``/``awaiting``/``state``),
the exit code second, exactly like ``run_workflow.py:classify_child_outcome`` — a
pre-contract child that exits 0 with ``ok:false`` is failed, never success.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from agentic_dynamics.runtime.executor import StepExecutor, StepRequest, StepResult

# scripts/fleet/ is a dir, not a package — add it beside scripts/ so the wrapper imports.
_FLEET_DIR = str(Path(__file__).resolve().parent)
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

import spawn_wrapper  # noqa: E402

from agentic_dynamics.experiment.experiment_spec import SCOPE_CONFIGS  # noqa: E402


class DockerAgentExecutor(StepExecutor):
    """Run each agent phase as a sibling cell container with its scope config.

    ``spec_path`` is the spec path AS THE SIBLING SEES IT (the launch broker mounts the repo
    at ``/repo`` per the request's mount profile, so ``/repo/<spec>``); ``spec_name`` is the
    workflow's name used for the per-attempt state namespace; ``cell_image`` is the sibling's
    image (``fleet/job-<name>`` or the default cell base), carried on the typed request.

    ``run_clone`` (fb1_clone_mounted — the clone is the cell's world) is the run's private
    ephemeral clone path (``PathConfig.runs_root/<run-id>/repo``). When set, every phase
    request this executor builds carries it (``build_phase_request(run_clone=...)``) and mounts
    the clone as the cell's repo — the launch broker binds ``runs_root/<run-id>/repo`` at
    ``/repo`` (rw for this commit-capable cell) and the shared worktree/``.git`` surface is
    absent from the request. It may be passed explicitly or inherited from the
    ``FINOPS_RUN_CLONE`` env var (a host-side launcher exports it to the workflow-runner tier);
    absent both, requests carry no clone — the pre-b2 shared-worktree shape unchanged.
    """

    def __init__(
        self,
        *,
        spec_path: str,
        spec_name: str,
        goal: str,
        model: str,
        workdir: str,
        backend: str | None = None,
        timeout: int = 1800,
        thinking_effort: str = "high",
        thinking_budget_tokens: int = 0,
        output_token_limit: int = 0,
        cell_image: str | None = None,
        run_clone: str | None = None,
        fork_checkpoint: str | None = None,
    ):
        self._spec_path = spec_path
        self._spec_name = spec_name
        self._goal = goal
        self._model = model
        self._workdir = workdir
        self._backend = backend
        self._timeout = timeout
        # The run's generation knobs must reach the CELL: the engine resolves them per
        # phase and the child re-runs the same spec, so a flag the orchestrator received
        # but the child does not would silently null the condition (the ladder's C2
        # thinking-budget arm depends on this).
        self._thinking_effort = thinking_effort
        self._thinking_budget_tokens = thinking_budget_tokens
        self._output_token_limit = output_token_limit
        self._cell_image = cell_image
        self._run_clone = run_clone or os.environ.get("FINOPS_RUN_CLONE")
        #: The pinned checkpoint id (``<workflow>/<attempt_id>``) this run's fork phases use;
        #: resolved ONCE at submit time so queued siblings cannot inherit different seeds.
        self._fork_checkpoint = str(fork_checkpoint or "")

    def build_request(self, request: StepRequest) -> dict[str, Any]:
        """Build the sibling-cell spawn request for ``request`` (pure, no docker).

        The admission in force (the engine entered ``phase_admission_scope`` before calling
        us) is stamped onto the spawn request as the lease block — a container inherits an
        environment, not a ContextVar. The run's clone path (fb1_clone_mounted), when one is
        configured, is carried on the request so the launch broker mounts the clone as the
        cell's repo — and the child runs INSIDE the clone (its ``--workdir`` is the clone's
        container mount point ``/repo``), so the cell's git operations and commits happen
        against ITS clone, never the shared worktree.
        """
        from agentic_dynamics.core.admission_context import current_context

        # fb1_clone_mounted: with a run clone the sibling operates in the clone, mounted at
        # /repo (spawn_wrapper/launch_broker REPO_TARGET) — the shared /tmp worktree namespace
        # is no longer mounted, so the cell's workdir IS the clone. Without a clone the cell
        # keeps operating in the shared-worktree path (pre-b2 shape, unchanged).
        sibling_workdir = spawn_wrapper.REPO_TARGET if self._run_clone else self._workdir
        # ws4_smoke (fleet_launch_smoke, exposed by THE SMOKE): the sibling command must name
        # the interpreter the CONTAINER resolves on PATH ("python3" = the fleet image's
        # /usr/local/bin/python3 — the interpreter the deps were installed under), never the
        # executor process's own sys.executable. The executor may run on the HOST (this wave's
        # in-process smoke drove it there), where sys.executable is the host's /usr/bin/python3
        # — a DIFFERENT interpreter that the fleet/base image also carries but with NO project
        # deps, so the child died at import before the suite ran. spawn_wrapper's own default
        # cell command ("python3 scripts/fleet/phase_runner.py") and the compose workflow-runner
        # command already use the PATH-resolved python3; the executors' sys.executable was the
        # one spot that baked a host path into a container argv.
        sibling_cmd = [
            "python3", "scripts/run_workflow.py",
            "--spec", self._spec_path,
            "--goal", self._goal,
            "--model", request.model or self._model,
            "--workdir", sibling_workdir,
            "--only-phase", request.phase_name,
            "--timeout", str(request.timeout or self._timeout),
            "--thinking-effort", self._thinking_effort,
        ]
        if self._thinking_budget_tokens:
            sibling_cmd += ["--thinking-budget-tokens", str(self._thinking_budget_tokens)]
        if self._output_token_limit:
            sibling_cmd += ["--output-token-limit", str(self._output_token_limit)]
        if self._backend or request.backend:
            sibling_cmd += ["--backend", self._backend or request.backend]
        # L29: the phase's agent role rides into the cell as the ordinary --agent flag; the
        # child's engine resolves it as its run default (empty = the adapter's worker pin).
        if request.agent:
            sibling_cmd += ["--agent", request.agent]
        # Isolated conversation forks: a phase may declare
        # ``fork_checkpoint: <repo-relative or absolute path to a seed run's data dir>``.
        # The parent stages the seed session's db beside the prepared step (same transport
        # dir, same .fleet commit exclusion) and stamps its identity onto the prepared step;
        # every child then stages its OWN copy into its isolated state dir. A declared fork
        # whose checkpoint is missing REFUSES here — before any launch, never a fresh session.
        fork_decl = None
        if isinstance(request.phase_def, dict):
            fork_decl = request.phase_def.get("fork_checkpoint")
            if fork_decl is None and request.phase_def.get("fork") is True:
                fork_decl = True
        if fork_decl is True:
            # The phase declares ITSELF a fork; the concrete checkpoint comes from the pinned
            # submission input — never a moving alias resolved per cell.
            if not self._fork_checkpoint:
                raise RuntimeError(
                    f"phase {request.phase_name!r} declares fork: true but this submission "
                    "pinned no --fork-checkpoint — refusing (a fork never falls back to fresh)"
                )
            fork_decl = {"ref": self._fork_checkpoint}
        if fork_decl:
            self._stage_fork_checkpoint(request, fork_decl)
        # Runner-owned transcripts default beneath the workdir; a read-only scope mount
        # (research_readonly / review_readonly / adversarial_readonly) cannot accept them.
        # Stamp a WRITABLE path under the cell's private state mount (``/state`` is rw) —
        # the adapter creates it on write; the default stays untouched for other scopes.
        scope = str(request.phase_def.get("scope") or "")
        if SCOPE_CONFIGS.get(scope, {}).get("results_mode") == "ro":
            attempt = max(int(request.attempt), 1)
            request.transcript_path = (
                f"/state/transcripts/{request.phase_name}.a{attempt}.session.jsonl"
            )
            # A read-only profile mounts the clone READ-ONLY: the adapter still initializes
            # the workdir (git init) and opencode writes project state in its CWD, so an agent
            # cell whose workdir is the ro clone cannot start (observed: zero tokens, no
            # session). Run the agent in a WRITABLE scratch beside its private state — the
            # repo stays readable at /repo (ro) via absolute paths — and create the host dir
            # now so the child's `--dir` exists at spawn time.
            request.workdir = f"{spawn_wrapper.STATE_TARGET}/workdir"
            # The prepared step stamps the CHILD-visible workdir from ``sibling_workdir``, so
            # the ro case must move that too — otherwise the child still runs in the ro clone.
            sibling_workdir = request.workdir
            if self._run_clone:
                run_key = Path(self._run_clone).parent.name
                host_scratch = (
                    Path(spawn_wrapper.STATE_ROOT)
                    / f"{self._spec_name}/{run_key}/{request.phase_name}/a{attempt}"
                    / "workdir"
                )
                host_scratch.mkdir(parents=True, exist_ok=True)

        # Step 3 (prepared-step transport): the parent readies the EXACT step (prompt + hash +
        # settings + attempt) and the child consumes it — never a re-derivation from the spec.
        # The transport's workdir is stamped with the CHILD-visible path (``sibling_workdir``),
        # so the concrete request is valid in the namespace it will execute in, not the parent's.
        prepared_path = self._write_prepared_step(request, workdir=sibling_workdir)
        sibling_cmd += ["--prepared-step", prepared_path]

        admission = current_context()
        # F3 (fleet_launch_container_smoke cs4): pass the phase's OWN declared scope as its
        # authorization. The phase_def carries ``scope: <vocabulary-member>`` (the declared
        # scope wins per the resolution order), and the executor is the composition-root side
        # that knows it — a custom spec's phases legitimately declare their scope, and the
        # static PHASE_SCOPE_AUTHORIZATION table cannot know them. Without this, step 2 falls
        # back to the table and REFUSES every custom-phase spawn (the F3 agent-cell gap: the
        # containerized path could only ever run table-known phases).
        phase_scopes = None
        declared = request.phase_def.get("scope") if isinstance(request.phase_def, dict) else None
        if declared in spawn_wrapper.SCOPE_VOCABULARY:
            phase_scopes = {request.phase_name: declared}
        # Step 3: the state namespace carries the RUN identity — <spec>/<run-id>/<phase> — so
        # two runs of the same spec never share one writable CLI-state directory (the
        # pre-step-3 <spec>/<phase> form did exactly that). The run id comes from the clone
        # path (runs_root/<run-id>/repo); in the legacy no-clone shape the run identity is
        # unknown and the namespace keeps its old form rather than fabricating one.
        run_key = Path(self._run_clone).parent.name if self._run_clone else ""
        attempt_key = f"a{max(int(request.attempt), 1)}"
        state_namespace = (
            f"{self._spec_name}/{run_key}/{request.phase_name}/{attempt_key}"
            if run_key
            else f"{self._spec_name}/{request.phase_name}/{attempt_key}"
        )
        return spawn_wrapper.build_phase_request(
            request.phase_def,
            goal=self._goal,
            workdir=sibling_workdir,
            model=request.model or self._model,
            spec_name=self._spec_name,
            command=sibling_cmd,
            admission=admission,
            run_clone=self._run_clone,
            phase_scopes=phase_scopes,
            state_namespace=state_namespace,
            # b3_launch_broker: the cell image + docker-side timeout ride on the TYPED request
            # (image_digest / timeout_seconds) — the executor no longer passes them to a docker
            # call of its own; the broker validates + executes them.
            image=self._cell_image,
            timeout_seconds=request.timeout or self._timeout or 0,
        )

    # ── checkpoint snapshots, receipts, and fork resolution ────────────────────────────

    def _snapshot_sqlite(self, src_db: Path, dest_db: Path) -> str:
        """Publish a COMPLETE standalone snapshot of ``src_db``; return the sha256 of the
        PUBLISHED bytes.

        SQLite's backup API copies a live database correctly (including content still in the
        source's WAL) into a fresh destination; the destination is switched out of WAL, closed
        and integrity-checked BEFORE hashing, so the digest covers the exact published bytes
        and never depends on a live sidecar. Publication is atomic (temp + ``os.replace``) and
        any stale destination sidecars are removed, so an earlier WAL can never resurrect.
        """
        import hashlib
        import os
        import sqlite3
        import tempfile

        dest_db.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(dest_db.parent), prefix=dest_db.name + ".")
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            src = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True)
            dst = sqlite3.connect(str(tmp))
            try:
                src.backup(dst)
                dst.execute("PRAGMA journal_mode=DELETE")
                row = dst.execute("PRAGMA integrity_check").fetchone()
                if not row or row[0] != "ok":
                    raise RuntimeError(f"snapshot integrity_check failed for {src_db}: {row}")
            finally:
                dst.close()
                src.close()
            digest = hashlib.sha256()
            with tmp.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    digest.update(chunk)
            os.replace(tmp, dest_db)
            for suffix in ("-wal", "-shm"):
                side = Path(str(dest_db) + suffix)
                if side.exists():
                    side.unlink()
            return digest.hexdigest()
        finally:
            if tmp.exists():
                tmp.unlink()

    @staticmethod
    def _session_present(db: Path, session_id: str) -> bool:
        import sqlite3

        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = con.execute(
                "select 1 from session where id = ? limit 1", (session_id,)
            ).fetchone()
            return row is not None
        finally:
            con.close()

    @staticmethod
    def _atomic_write(directory: Path, name: str, payload: str) -> None:
        """Write ``payload`` to ``directory/name`` via a UNIQUE temp file + atomic replace.

        Unique temps (``tempfile.mkstemp``) remove the concurrent-writer collision on a shared
        ``.tmp`` path; the replace makes the publication atomic, so an interrupted write can
        never leave a malformed final file behind.
        """
        import os
        import tempfile

        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, directory / name)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _session_identity(db: Path) -> str:
        """Stable identity of a snapshot's CONVERSATION contents (not SQLite bookkeeping).

        Sorted session ids with their message counts — unchanged by -shm churn, a WAL
        checkpoint, or page-level repacking; changed when the conversation changed.
        """
        import hashlib
        import sqlite3

        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = list(con.execute("select id from session order by id"))
            try:
                counts = dict(con.execute("select session_id, count(*) from message group by session_id"))
            except sqlite3.Error:
                counts = {}
        finally:
            con.close()
        lines = [f"{r[0]}:{counts.get(r[0], 0)}" for r in rows]
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    def _store_root(self) -> Path:
        from agentic_dynamics.core.paths import PROJECT_ROOT

        return Path(PROJECT_ROOT) / "experiments" / "results" / "opencode"

    def _resolve_fork_source(self, decl: object) -> tuple[Path, str, str]:
        """Resolve a ``fork_checkpoint`` declaration to (snapshot db, session id, receipt sha).

        Accepted forms — every field REQUIRED (an incomplete declaration refuses):

        * ``{ref: "latest:<workflow>"}``    — the workflow's latest published receipt;
        * ``{ref: "<workflow>/<receipt>"}`` — a named per-attempt receipt;
        * ``{path: "...", session_id: "ses_..."}`` — an explicit snapshot/data-dir + parent.
        """
        import json

        from agentic_dynamics.core.paths import PROJECT_ROOT

        store_root = self._store_root()
        if isinstance(decl, str):
            decl = {"path": decl}
        if not isinstance(decl, dict):
            raise RuntimeError(
                f"fork_checkpoint declaration must be a mapping or path, got {type(decl).__name__}"
            )
        ref = str(decl.get("ref") or "")
        if ref:
            if ref.startswith("latest:"):
                workflow = ref.split(":", 1)[1]
                receipt_path = store_root / workflow / "latest.json"
            else:
                workflow, _, rid = ref.partition("/")
                receipt_path = store_root / workflow / "receipts" / f"{rid}.json"
            if not receipt_path.is_file():
                raise RuntimeError(
                    f"fork_checkpoint ref {ref!r}: no published receipt at {receipt_path} — refusing"
                )
            rec = json.loads(receipt_path.read_text(encoding="utf-8"))
            session_id = str(rec.get("session_id") or "")
            snapshot = str(rec.get("snapshot") or "")
            wf = str(rec.get("workflow") or workflow)
            if not session_id or not snapshot:
                raise RuntimeError(
                    f"fork_checkpoint ref {ref!r}: receipt lacks session_id/snapshot — refusing"
                )
            return store_root / wf / snapshot, session_id, str(rec.get("sha256") or "")
        path = str(decl.get("path") or "")
        session_id = str(decl.get("session_id") or "")
        if not path or not session_id:
            raise RuntimeError(
                "fork_checkpoint requires an explicit parent session_id and a path — refusing"
            )
        seed = Path(path)
        if not seed.is_absolute():
            seed = Path(PROJECT_ROOT) / seed
        return seed / "opencode" / "opencode.db", session_id, ""

    def _stage_fork_checkpoint(self, request: StepRequest, decl: object) -> None:
        """Publish the approved parent snapshot beside the prepared step + stamp the identity.

        The declaration resolves to an explicit parent session; the session must EXIST in the
        source (a newer delegated session is never chosen implicitly); the source bytes must
        match the receipt's advertised digest when it carries one; the transported bytes are a
        fresh standalone snapshot whose digest the child re-verifies. Any failure refuses
        before launch — a declared fork never degrades to a fresh session.
        """
        if not self._run_clone:
            raise RuntimeError("fork_checkpoint requires a run clone")
        src_db, session_id, receipt_sha = self._resolve_fork_source(decl)
        if not src_db.is_file():
            raise RuntimeError(f"fork_checkpoint source missing at {src_db} — refusing")
        if receipt_sha:
            import hashlib

            actual = hashlib.sha256(src_db.read_bytes()).hexdigest()
            if actual != receipt_sha:
                raise RuntimeError(
                    f"fork_checkpoint source {src_db} changed since publication "
                    f"({actual[:12]} != {receipt_sha[:12]}) — refusing"
                )
        if not self._session_present(src_db, session_id):
            raise RuntimeError(
                f"fork_checkpoint: parent session {session_id} is not present in {src_db} — refusing"
            )
        dest_dir = Path(self._run_clone) / ".fleet" / "fork_checkpoints"
        dest = dest_dir / f"{request.phase_name}.a{max(int(request.attempt), 1)}.db"
        digest = self._snapshot_sqlite(src_db, dest)
        request.fork_session_id = session_id
        request.fork_checkpoint_sha256 = digest
        request.fork_db_path = (
            f"{spawn_wrapper.REPO_TARGET}/.fleet/fork_checkpoints/{dest.name}"
        )

    def _persist_session_state(
        self, request: StepRequest, *, session_id: str = ""
    ) -> tuple[str, str]:
        """Publish the completed cell's session as an immutable per-attempt receipt.

        Returns ``(checkpoint_ref, archive_error)``. The snapshot is a complete standalone db
        (SQLite backup API) published atomically under
        ``experiments/results/opencode/<workflow>/snapshots/<run>-<phase>.a<n>.db``; the receipt
        at ``receipts/<run>-<phase>.a<n>.json`` is IMMUTABLE (re-publishing identical bytes is
        idempotent; different bytes at the same identity are refused, never silently replaced);
        ``latest.json`` is an atomically replaced pointer for ``ref: latest:<workflow>``. A
        missing cell db is ``unavailable`` — an ordinary run keeps its result, but a workflow
        without a receipt is not fork-ready.
        """
        import json
        from datetime import datetime, timezone

        if not self._run_clone:
            return "", "no run clone"
        run_key = Path(self._run_clone).parent.name
        attempt = max(int(request.attempt), 1)
        namespace = f"{self._spec_name}/{run_key}/{request.phase_name}/a{attempt}"
        src = Path(spawn_wrapper.STATE_ROOT) / namespace / "data" / "opencode" / "opencode.db"
        if not src.is_file():
            return "", f"no cell session db at {src}"
        store = self._store_root() / self._spec_name
        (store / "snapshots").mkdir(parents=True, exist_ok=True)
        (store / "receipts").mkdir(parents=True, exist_ok=True)
        attempt_id = f"{run_key}-{request.phase_name}.a{attempt}"
        snapshot_rel = f"snapshots/{attempt_id}.db"
        snapshot = store / snapshot_rel
        receipt_path = store / "receipts" / f"{attempt_id}.json"
        if receipt_path.is_file():
            import json as _json

            try:
                prior = _json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    f"receipt {receipt_path} is unreadable/malformed ({exc}) — refusing; "
                    "remove it deliberately to re-publish"
                ) from exc
            published = store / str(prior.get("snapshot") or snapshot_rel)
            import hashlib

            if not published.is_file() or hashlib.sha256(published.read_bytes()).hexdigest() != str(prior.get("sha256") or ""):
                raise RuntimeError(
                    f"published snapshot {published} is missing or does not match its receipt — refusing"
                )
            # Identity is based on STABLE snapshot contents (the session set + message counts),
            # never transient SQLite bookkeeping: the backup itself can touch -shm, and a WAL
            # checkpoint can empty -wal, without the conversation having changed.
            probe = store / "snapshots" / f".{attempt_id}.probe.db"
            try:
                self._snapshot_sqlite(src, probe)
                fresh_identity = self._session_identity(probe)
            finally:
                probe.unlink(missing_ok=True)
            if fresh_identity != str(prior.get("session_identity") or ""):
                raise RuntimeError(
                    f"checkpoint identity {attempt_id} already published with different "
                    "conversation contents — refusing to replace evidence (publish a new "
                    "attempt instead)"
                )
            return f"{self._spec_name}/{attempt_id}", ""
        digest = self._snapshot_sqlite(src, snapshot)
        session_identity = self._session_identity(snapshot)
        receipt = {
            "schema": "opencode-checkpoint/v1",
            "workflow": self._spec_name,
            "attempt_id": attempt_id,
            "run_id": run_key,
            "phase": request.phase_name,
            "attempt": attempt,
            "snapshot": snapshot_rel,
            "sha256": digest,
            "session_identity": session_identity,
            "session_id": session_id,
            "forked_from": request.fork_session_id or "",
            "prepared_prompt_sha256": request.prompt_sha256,
            "runtime": {"opencode": "1.18.15"},
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        self._atomic_write(store / "receipts", f"{attempt_id}.json", payload)
        # ``latest.json`` is a POINTER, not evidence: publish it with a UNIQUE temp name so
        # concurrent completions never collide on one shared temp path (the reproduced
        # FileNotFoundError cleared a valid reference), then replace atomically. The receipt
        # above is the immutable record; the pointer is last-writer-wins by design.
        self._atomic_write(store, "latest.json", payload)
        return f"{self._spec_name}/{attempt_id}", ""

    def _prepared_relative_path(self, request: StepRequest) -> str:
        """The CLONE-RELATIVE prepared-step path for ``request`` (the reference the ledger keeps).

        ``_write_prepared_step`` names the transport ``<phase>.a<attempt>.json``; this is the
        same name without the absolute mount root (``/repo`` or the host workdir), so the run
        ledger and the drawer can point at the exact instruction that was delivered without
        baking a host- or container-specific prefix into durable evidence.
        """
        return f".fleet/prepared_steps/{request.phase_name}.a{max(int(request.attempt), 1)}.json"

    def _write_prepared_step(self, request: StepRequest, *, workdir: str | None = None) -> str:
        """Write the prepared step where the CHILD reads it; return the child-visible path.

        The file travels inside the run clone (mounted at ``/repo`` in the sibling), so the
        parent's write path and the child's read path differ only by the mount root. A
        local-only ``.git/info/exclude`` entry keeps the transport out of the cell's commits
        (no tracked file changes). Without a clone the legacy shared-worktree shape is used,
        where the host path IS the child path.
        """
        phase_file = f"{request.phase_name}.a{max(int(request.attempt), 1)}.json"
        if self._run_clone:
            host_dir = Path(self._run_clone) / ".fleet" / "prepared_steps"
            child_path = f"{spawn_wrapper.REPO_TARGET}/.fleet/prepared_steps/{phase_file}"
            exclude = Path(self._run_clone) / ".git" / "info" / "exclude"
            # A fresh run clone may not carry ``.git/info/`` at all (git init/clone shapes
            # differ). The original ``is_dir()`` guard skipped the exclusion SILENTLY in that
            # case, and the engine's post-phase ``git add -A`` then committed the transport
            # file into the candidate (observed on main: ``.fleet/prepared_steps/fit.a1.json``
            # and ``journey.a1.json``). Create ``info/`` when the clone's own ``.git`` is a
            # directory so the documented exclusion always lands.
            if (exclude.parent.parent).is_dir():
                exclude.parent.mkdir(parents=True, exist_ok=True)
            if exclude.parent.is_dir():
                line = ".fleet/prepared_steps/"
                text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
                if line not in text.splitlines():
                    separator = "" if not text or text.endswith("\n") else "\n"
                    exclude.write_text(f"{text}{separator}{line}\n", encoding="utf-8")
        else:
            host_dir = Path(self._workdir) / ".fleet" / "prepared_steps"
            child_path = str(host_dir / phase_file)
        host_dir.mkdir(parents=True, exist_ok=True)
        (host_dir / phase_file).write_text(
            json.dumps(request.to_prepared_dict(workdir=workdir), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return child_path

    def execute(self, request: StepRequest) -> StepResult:
        """Spawn one sibling cell for ``request`` (via the launch broker) and classify its outcome."""
        phase_request = self.build_request(request)
        # F3 (fleet_launch_container_smoke cs4): the spawn-side re-validation needs the phase's
        # own declared scope as its authorization (spawn_sibling's step-2 check) — a custom
        # spec's phase legitimately declares its scope; the static table cannot know it.
        auth_scopes = None
        declared = request.phase_def.get("scope") if isinstance(request.phase_def, dict) else None
        if declared in spawn_wrapper.SCOPE_VOCABULARY:
            auth_scopes = {request.phase_name: declared}
        outcome = spawn_wrapper.spawn_sibling(phase_request, phase_scopes=auth_scopes)
        decision = _classify(outcome)
        state = decision["state"]
        envelope = decision.get("envelope") or {}

        sr = StepResult(
            ok=state == "ok",
            state=state,
            error=str(envelope.get("error") or outcome.get("stderr", ""))[:800],
            exit_code=int(outcome.get("returncode", -1) or -1),
        )
        # Run-inspection slice: the parent wrote the prepared-step transport for this step in
        # ``build_request`` above. Record its clone-relative path + prompt hash so the phase
        # result (and the run ledger) can point at the exact instruction delivered. The parent
        # computed value is the default; a child envelope that already carries the reference
        # wins because it is first-hand.
        sr.prepared_step_path = self._prepared_relative_path(request)
        sr.prepared_step_prompt_sha256 = request.prompt_sha256
        phase = _phase_from_envelope(envelope)
        if phase is not None:
            if phase.get("prepared_step_path"):
                sr.prepared_step_path = str(phase["prepared_step_path"])
            if phase.get("prepared_step_prompt_sha256"):
                sr.prepared_step_prompt_sha256 = str(phase["prepared_step_prompt_sha256"])
            sr.session_id = str(phase.get("session_id", "") or "")
            sr.total_tokens = int(phase.get("tokens", {}).get("total", 0) or 0)
            sr.prompt_tokens = int(phase.get("tokens", {}).get("in", 0) or 0)
            sr.completion_tokens = int(phase.get("tokens", {}).get("out", 0) or 0)
            sr.reasoning_tokens = int(phase.get("tokens", {}).get("reasoning", 0) or 0)
            sr.answer_tokens = int(phase.get("tokens", {}).get("answer", 0) or 0)
            sr.explanation_tokens = int(phase.get("tokens", {}).get("explanation", 0) or 0)
            sr.estimated_cost_usd = float(phase.get("cost_usd", 0.0) or 0.0)
            sr.files_created = list(phase.get("files_created", []) or [])
            sr.files_modified = list(phase.get("files_modified", []) or [])
            # Measurement carry-through (Astra review item 9/6): the child envelope carries
            # cache economics + cost provenance; the parent ledger must see them or the
            # experiment cannot report anything but manual SQLite numbers.
            sr.cache_read_tokens = int(phase.get("cache_read_tokens", 0) or 0)
            sr.cache_write_tokens = int(phase.get("cache_write_tokens", 0) or 0)
            sr.cache_hit_rate = float(phase.get("cache_hit_rate", 0.0) or 0.0)
            sr.first_token_at = phase.get("first_token_at")
            sr.cost_source = str(phase.get("cost_source", "") or "") or sr.cost_source
            sr.reported_cost_usd = phase.get("reported_cost_usd")
            sr.estimation_method = phase.get("estimation_method")
            # Changed-set availability (evidence-validity finding 8b): a snapshot-skipped
            # git-status observation is partial; carry the provenance across the container
            # boundary exactly as the in-process path does.
            sr.change_detection = str(phase.get("change_detection", "") or "")
            sr.change_observation_partial = bool(phase.get("change_observation_partial", False))
            sr.confidence = phase.get("confidence")
            sr.final_response = str(phase.get("final_response", "") or "")
        # Durable workflow session store (operator direction 2026-09-19): the cell's db was
        # never shared while it ran, and it does not share one afterwards either — the finished
        # session is PERSISTED as its OWN file under experiments/results/opencode/<workflow>/,
        # with a lineage entry in the workflow manifest. Best-effort: no db records nothing and
        # never fails the phase.
        try:
            sr.checkpoint_ref, sr.archive_error = self._persist_session_state(
                request, session_id=sr.session_id
            )
        except Exception as exc:  # a seed without a checkpoint is not fork-ready; surface it
            sr.checkpoint_ref, sr.archive_error = "", str(exc)[:300]
        return sr


def resolve_checkpoint_ref(ref: str, *, store_root: Path | None = None) -> str:
    """Resolve a checkpoint reference ONCE to a pinned ``<workflow>/<attempt_id>``.

    ``latest:<workflow>`` is a moving pointer; any consumer that must be stable across queued
    siblings (the branch submissions) resolves it HERE, at submit time, and carries the pinned
    id. A missing receipt refuses — a branch is never submitted against an unpublished seed.
    """
    import json

    if not ref:
        raise RuntimeError("empty checkpoint reference")
    store = store_root or (
        _store_root_path()
    )
    if ref.startswith("latest:"):
        workflow = ref.split(":", 1)[1]
        receipt_path = store / workflow / "latest.json"
        if not receipt_path.is_file():
            raise RuntimeError(f"checkpoint ref {ref!r}: no published receipt at {receipt_path}")
        rec = json.loads(receipt_path.read_text(encoding="utf-8"))
        attempt_id = str(rec.get("attempt_id") or "")
        if not attempt_id:
            raise RuntimeError(f"checkpoint ref {ref!r}: latest receipt lacks an attempt_id")
        return f"{workflow}/{attempt_id}"
    workflow, _, attempt_id = ref.partition("/")
    if not workflow or not attempt_id:
        raise RuntimeError(f"checkpoint ref {ref!r} must be '<workflow>/<attempt_id>'")
    receipt_path = store / workflow / "receipts" / f"{attempt_id}.json"
    if not receipt_path.is_file():
        raise RuntimeError(f"checkpoint ref {ref!r}: no published receipt at {receipt_path}")
    return f"{workflow}/{attempt_id}"


def _store_root_path() -> Path:
    from agentic_dynamics.core.paths import PROJECT_ROOT

    return Path(PROJECT_ROOT) / "experiments" / "results" / "opencode"


def _phase_from_envelope(envelope: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the single phase's record out of the child's run envelope."""
    phases = envelope.get("phases") or []
    if not phases:
        return None
    return dict(phases[0])


def _classify(outcome: dict[str, Any]) -> dict[str, Any]:
    """Classify the spawned sibling's outcome: envelope-first, exit-code fallback.

    Mirrors ``run_workflow.py:classify_child_outcome`` (the P0-1 contract): never trust
    ``returncode == 0`` alone — a pre-contract child exits 0 with ``ok:false`` or
    ``awaiting:true``. Kept here (not imported) so the executor has zero dependencies
    on the CLI script and no import cycle.
    """
    stdout = outcome.get("stdout", "") or ""
    returncode = outcome.get("returncode")
    envelope = _parse_envelope(stdout)
    if returncode == 10:
        return {"state": "awaiting", "envelope": envelope}
    if returncode not in (None, 0):
        return {"state": "failed", "envelope": envelope}
    if envelope is not None:
        if envelope.get("awaiting") is True:
            return {"state": "awaiting", "envelope": envelope}
        if envelope.get("ok") is False:
            return {"state": "failed", "envelope": envelope}
    return {"state": "ok", "envelope": envelope}


def _parse_envelope(stdout: str) -> dict[str, Any] | None:
    """Best-effort parse of the child's final result envelope (its last JSON document)."""
    if not stdout:
        return None
    lines = stdout.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() != "{":
            continue
        try:
            obj = json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "ok" in obj:
            return obj
    return None
