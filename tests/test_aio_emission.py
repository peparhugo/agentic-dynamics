"""AIO permanence-decision emission guard (Wave-3 a5_aio_emission).

``a5`` makes the AIO observable: the permanence verbs it routes — a promote request, a publish
request, an approval — emit into the knowledge base through the existing producers AT THE
CALL SITE (``scripts/promote.py``, ``scripts/publish_release.py``): an observation record (via
``observation_ingestion``) for each decision, and an actuation record (via
``actuation_ingestion.derive_actuation_record`` — the first PERMANENCE caller) whose ``causes``
links back to the observation that justified it.

The guard proves the a5 contract in both directions:

* **(a) a promote decision emits an observation** with the run_id + candidate_sha (+ operator) —
  unit-level through ``aio_emission.build_observation`` and end-to-end through the real promote
  call site publishing onto a fake knowledge stream;
* **(b) a promote act emits an actuation record whose causes link to that observation** and the
  lineage gate passes — the observation is indexed before the actuation publishes, so
  ``publish_event``'s ``causes``-must-resolve-to-an-observation check accepts it;
* **(c) the emission is best-effort** — a producer failure (downed stream, a raising emitter)
  never blocks the act (the push/deploy still happens);
* **(d) actuation_ingestion now has a permanence caller** (per the a0 preregistration's D-2, the
  true residual: the Control Room steer/interrupt emit and the shadow-decision recorder already
  existed — no promote/publish/approval decision emitted; ``aio_emission.build_actuation`` is
  that caller).

The pure-derivation tests need no store (a fake Redis stands in for the stream's three-method
surface); the call-site integration tests build a real tmp git worktree + a fake push, exactly
as ``test_promote`` / ``test_publish_release`` do for their own seams — so this module (like
those) is deliberately NOT ``fast``-marked: it exercises the real git/control-db paths.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = str(ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import publish_release as pr  # noqa: E402
from promote import _promote_decision, _run_promotion  # noqa: E402

from agentic_dynamics.control import aio_emission  # noqa: E402
from agentic_dynamics.knowledge.knowledge import Authority, message_family  # noqa: E402

# ── the decision fixture ──────────────────────────────────────────────────────

_CANDIDATE_SHA = "941cd79f2531bd43f594a43eef26ad416460c9e3"


def _decision(**overrides) -> dict:
    decision = {
        "verb": "promote",
        "run_id": "authoring_product_aio@0.1",
        "candidate_sha": _CANDIDATE_SHA,
        "operator": "drseuss",
        "status": "requested",
        "why": "wave3 a5",
    }
    decision.update(overrides)
    return decision


# ── a fake knowledge stream (hset/hget/xadd — the exact surface publish_event touches) ──


class _FakeRedis:
    """In-memory stand-in for the knowledge-stream Redis (DB 2 on 6380).

    Implements only the surface ``knowledge_stream.publish_event`` touches: ``hset``/``hget`` on
    the source-type index (the actuation lineage gate) and ``xadd`` on the change stream. A
    publish that the gate rejects raises before ``xadd``, so the presence of an actuation entry
    in ``stream`` IS the proof that the lineage check passed.
    """

    def __init__(self):
        self.index: dict[str, str] = {}
        self.stream: dict[str, dict] = {}
        self._n = 0

    def hset(self, key, field, value):  # noqa: A003 - redis-shaped surface
        self.index[field] = value

    def hget(self, key, field):
        return self.index.get(field)

    def xadd(self, stream, payload):
        self._n += 1
        entry_id = f"1-{self._n}"
        self.stream[entry_id] = payload
        return entry_id


# ═════════════════════════════════════════════════════════════════════════════
# (a) + (b) — pure derivation over the two producers
# ═════════════════════════════════════════════════════════════════════════════


class TestBuildObservation:
    def test_promote_decision_observation_carries_run_id_and_candidate_sha(self):
        obs = aio_emission.build_observation(_decision())
        # the observation producer's subject IS the run the candidate came from.
        assert obs.source_type == "observation"
        assert obs.subject_id == "authoring_product_aio@0.1"
        assert obs.subject_status == "promote:requested"
        # the candidate sha + operator ride in the record's text (the producer's why slot).
        assert _CANDIDATE_SHA in obs.text
        assert "operator drseuss" in obs.text
        assert obs.authority is Authority.ADVISORY and obs.evidence_class == "[H]"

    def test_publish_decision_observation_is_symmetric(self):
        obs = aio_emission.build_observation(_decision(verb="publish", status="requested"))
        assert obs.subject_id == "authoring_product_aio@0.1"
        assert obs.subject_status == "publish:requested"
        assert _CANDIDATE_SHA in obs.text

    def test_observation_without_candidate_sha_refuses(self):
        with pytest.raises(ValueError, match="no candidate_sha"):
            aio_emission.build_observation(_decision(candidate_sha=""))

    def test_unknown_verb_refuses(self):
        with pytest.raises(ValueError, match="unknown verb"):
            aio_emission.build_observation(_decision(verb="merge"))

    def test_run_id_falls_back_to_candidate_for_storeless_callers(self):
        obs = aio_emission.build_observation(_decision(run_id=""))
        assert obs.subject_id.startswith("promote:")
        assert _CANDIDATE_SHA in obs.text


class TestBuildActuation:
    def test_promote_act_actuation_causes_link_to_the_decision_observation(self):
        obs = aio_emission.build_observation(_decision())
        act = aio_emission.build_actuation(
            _decision(requested_action={"outcome": "pushed", "pushed_sha": "abc123"}),
            causes=obs.knowledge_id,
        )
        assert act.source_type == "actuation"
        assert act.authority is Authority.POLICY and act.evidence_class == "[P]"
        assert act.causes == obs.knowledge_id
        # the body names the act: verb, run, requested_by = operator, and the candidate.
        body = json.loads(act.text)
        assert body["actuation_kind"] == "promote"
        assert body["target_session_id"] == "authoring_product_aio@0.1"
        assert body["requested_by"] == "drseuss"
        assert body["requested_action"]["candidate_sha"] == _CANDIDATE_SHA
        assert body["requested_action"]["pushed_sha"] == "abc123"

    def test_empty_causes_refuses_at_construction(self):
        # the producer's one hard construction-time requirement is preserved through the seam.
        with pytest.raises(ValueError, match="no `causes`"):
            aio_emission.build_actuation(_decision(), causes="")

    def test_family_routing_is_correct(self):
        obs = aio_emission.build_observation(_decision())
        act = aio_emission.build_actuation(_decision(), causes=obs.knowledge_id)
        assert message_family(obs.source_type) == "observation"
        assert message_family(act.source_type) == "actuation"


# ═════════════════════════════════════════════════════════════════════════════
# (b) + (c) — the lineage gate + best-effort over a (fake) knowledge stream
# ═════════════════════════════════════════════════════════════════════════════


class TestPublishLineage:
    def test_observation_then_actuation_passes_the_lineage_gate(self):
        """An actuation published after its justifying observation is accepted (causes resolve)."""
        redis = _FakeRedis()
        out = aio_emission.emit_decision(_decision(), connect_fn=lambda: redis)
        assert len(out["entry_ids"]) == 1  # the observation landed (and was indexed)
        act_out = aio_emission.emit_act(
            _decision(requested_action={"outcome": "pushed", "pushed_sha": "abc"}),
            causes=out["observation"].knowledge_id,
            connect_fn=lambda: redis,
        )
        assert len(act_out["entry_ids"]) == 1  # the actuation landed — the gate PASSED
        assert len(redis.stream) == 2
        # the actuation event carries the observation's knowledge_id as its causes.
        act_event = list(redis.stream.values())[1]
        assert act_event["causes"] == out["observation"].knowledge_id
        assert act_event["knowledge_id"] == act_out["actuation"].knowledge_id

    def test_actuation_without_a_registered_observation_is_rejected_best_effort(self):
        """An actuation whose causes never resolved is refused by the gate — closed by default.

        ``publish`` swallows the rejection (best-effort) and returns no entry id: a causeless
        permanence act is not emitted even when the emitter tries, so the AIO's acts stay
        auditable by construction.
        """
        redis = _FakeRedis()
        act = aio_emission.build_actuation(_decision(), causes="never-indexed-observation")
        entry_ids = aio_emission.publish([act], connect_fn=lambda: redis)
        assert entry_ids == []
        assert redis.stream == {}

    def test_downed_stream_is_a_warning_not_an_error(self):
        """A producer failure never raises — the emit returns the record and an empty id list."""
        def down():
            raise ConnectionError("redis is down")

        out = aio_emission.emit_decision(_decision(), connect_fn=down)
        assert out["entry_ids"] == []
        assert out["observation"].subject_id == "authoring_product_aio@0.1"  # still derived
        act_out = aio_emission.emit_act(
            _decision(), causes=out["observation"].knowledge_id, connect_fn=down,
        )
        assert act_out["entry_ids"] == []
        assert act_out["actuation"].causes == out["observation"].knowledge_id


# ═════════════════════════════════════════════════════════════════════════════
# (a) + (b) + (c) — the promote CALL SITE emits (end to end, real default emitters)
# ═════════════════════════════════════════════════════════════════════════════

_GOAL_PREFIX = "g"  # the ledger/test commit subject pattern


def _candidate_worktree(tmp_path: Path) -> tuple[Path, str, str]:
    """A real git worktree: main at a base commit + a feature branch with one [workflow] commit.

    Returns ``(wt, base_sha, feature_head_sha)`` — the promote real path needs a candidate
    whose ``base..HEAD`` diff is non-empty (unlike ``test_promote``'s dry-run fixtures, which
    never reach the push).
    """
    wt = tmp_path / "candidate"
    wt.mkdir()
    for argv in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(argv, cwd=wt, check=True)
    (wt / "base.py").write_text("BASE = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=wt, check=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "branch", "-m", "main"], cwd=wt, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=wt, check=True)
    (wt / "calc.py").write_text("def add(a, b): return a + b\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"[workflow] scope — {_GOAL_PREFIX}"], cwd=wt, check=True)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    return wt, base_sha, head_sha


def _promote_args(tmp_path: Path, wt: Path, ledger: dict, **overrides):
    from types import SimpleNamespace

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(ledger))
    args = {
        "spec": "promote_test",
        "workdir": str(wt),
        "ledger": str(ledger_path),
        "approval": None,
        "base": "main",
        "operator": "drseuss",
        "dry_run": False,
    }
    args.update(overrides)
    return SimpleNamespace(**args)


def _ledger(head_sha: str, **overrides) -> dict:
    data = {
        "spec_name": "promote_test",
        "spec_id": "promote_test@0.1",
        "git_sha": head_sha,
        "ok": True,
        "state": "succeeded",
        "total_cost_usd": 0.001,
        "phases": [
            {"phase": "scope", "kind": "agent", "status": "ok",
             "commit_hash": head_sha, "test_executed_success": None},
            {"phase": "verify", "kind": "test", "status": "ok",
             "commit_hash": head_sha, "test_executed_success": True},
        ],
    }
    data.update(overrides)
    return data


def _fake_push(calls: list):
    def push(workdir, base, subject, candidate):
        calls.append((str(workdir), base, subject, candidate))
        return "feedfacefeedfacefeedface"
    return push


class TestPromoteCallSiteEmits:
    def test_promote_decision_and_act_emit_end_to_end(self, tmp_path, monkeypatch):
        """Run the real promote path against a fake knowledge stream + fake push.

        The default a5 emitters publish through ``knowledge_stream.publish_event``; pointing
        ``ks.connect`` at a fake Redis makes the whole lineage gate run for real — the
        observation must be indexed before the actuation's ``causes`` resolves, or the
        actuation entry never lands. The producers' clock is frozen so the streamed event ids
        are reproducible offline (the observation producer folds its timestamp into identity
        deliberately).
        """
        from agentic_dynamics.control import actuation_ingestion as ai
        from agentic_dynamics.control import observation_ingestion as oi
        from agentic_dynamics.knowledge import knowledge_ingestion as ki
        from agentic_dynamics.knowledge import knowledge_stream as ks
        from agentic_dynamics.knowledge import record_factory

        fixed_clock = "2026-09-03T00:00:00+00:00"
        for mod in (record_factory, ki, oi, ai):
            monkeypatch.setattr(mod, "_now_iso", lambda now=None: fixed_clock)

        wt, _base, head = _candidate_worktree(tmp_path)
        ledger = _ledger(head)
        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        pushes: list = []
        args = _promote_args(tmp_path, wt, ledger)
        _run_promotion(args, push=_fake_push(pushes))

        assert len(pushes) == 1  # the act happened
        # the decision dict the call site built (deterministic from args+ledger) is what the
        # observation must carry: run_id + candidate_sha + operator.
        decision = _promote_decision(args, ledger, head, status="requested")
        assert decision["run_id"] == "promote_test@0.1"
        assert decision["candidate_sha"] == head
        assert decision["operator"] == "drseuss"

        # (a) the streamed observation is exactly that decision's record — carrying run_id
        # (subject_id) + candidate sha (in its text) — and it landed BEFORE the actuation.
        obs = aio_emission.build_observation(decision)
        events = list(redis.stream.values())
        assert len(events) == 2
        assert events[0]["knowledge_id"] == obs.knowledge_id
        assert obs.subject_id == "promote_test@0.1"
        assert head in obs.text
        assert "operator drseuss" in obs.text
        assert events[0]["causes"] == ""  # the observation has no causes of its own

        # (b) the actuation landed too — its presence in the stream proves the lineage gate
        # passed — and its causes is the observation's knowledge_id (derived via the producers).
        assert events[1]["causes"] == obs.knowledge_id
        assert events[1]["knowledge_id"] != obs.knowledge_id

    def test_capturing_emitters_receive_decision_then_act_with_threaded_causes(self, tmp_path):
        """The call site threads the observation id into the act's causes (no second observer)."""
        wt, _base, head = _candidate_worktree(tmp_path)
        ledger = _ledger(head)
        calls = {"decision": [], "act": []}
        observation_ids: list = []

        def emit_decision(decision):
            calls["decision"].append(decision)
            obs_id = aio_emission.build_observation(decision).knowledge_id
            observation_ids.append(obs_id)
            return {"observation_id": obs_id, "entry_ids": ["1-1"]}

        def emit_act(decision, *, causes):
            calls["act"].append((decision, causes))
            return {"actuation_id": "act-1", "entry_ids": ["1-2"]}

        _run_promotion(
            _promote_args(tmp_path, wt, ledger),
            push=_fake_push([]), emit_decision=emit_decision, emit_act=emit_act,
        )

        assert len(calls["decision"]) == 1
        assert len(calls["act"]) == 1
        decision, causes = calls["act"][0]
        assert calls["decision"][0]["candidate_sha"] == head
        # the act's causes == the observation id the decision emitter returned.
        assert causes == observation_ids[0]
        assert decision["requested_action"]["outcome"] == "pushed"
        assert decision["requested_action"]["pushed_sha"] == "feedfacefeedfacefeedface"

    def test_emission_failure_never_blocks_the_act(self, tmp_path):
        """(c) best-effort is structural: a raising emitter cannot stop a verified promotion."""
        wt, _base, head = _candidate_worktree(tmp_path)
        ledger = _ledger(head)
        pushes: list = []

        def boom_decision(decision):
            raise RuntimeError("observation producer exploded")

        def boom_act(decision, *, causes):
            raise RuntimeError("actuation producer exploded")

        # must not raise — the act proceeds even though both emissions failed.
        _run_promotion(
            _promote_args(tmp_path, wt, ledger),
            push=_fake_push(pushes), emit_decision=boom_decision, emit_act=boom_act,
        )
        assert len(pushes) == 1

    def test_dry_run_emits_nothing(self, tmp_path):
        """A dry run is a plan, not a permanence decision — no observation, no actuation."""
        wt, _base, head = _candidate_worktree(tmp_path)
        ledger = _ledger(head)
        calls: list = []
        _run_promotion(
            _promote_args(tmp_path, wt, ledger, dry_run=True),
            push=_fake_push([]),
            emit_decision=lambda d: calls.append(("decision", d)) or {},
            emit_act=lambda d, **kw: calls.append(("act", d)) or {},
        )
        assert calls == []  # nothing emitted, nothing pushed


# ═════════════════════════════════════════════════════════════════════════════
# the publish CALL SITE emits (mirror wiring — decision before deploy, act on success)
# ═════════════════════════════════════════════════════════════════════════════


def _publish_env(tmp_path, monkeypatch) -> Path:
    """A ready real-publish-path environment mirroring test_publish_release's fixtures.

    Returns the tmp control-db path; patches ``read_head_sha`` + the publication module's site
    root so the real (non-dry-run) transaction is runnable without a checkout or Firebase.
    """
    import datetime

    from agentic_dynamics.control import publication as pub
    from agentic_dynamics.control.control_db import ControlDB

    db_path = tmp_path / "control.db"
    with ControlDB.open(db_path) as db:
        for proj in ("registry", "chroma", "neo4j"):
            db.record_watermark(
                proj, last_event_id="e1", source_head_event_id="e1",
                lag_events=0,
                last_success_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<p>1,027 story sessions</p>")
    (site / "data.js").write_text(
        "window.DYNAMICS_DATA = " + json.dumps({"public_statistics": {"story_sessions": 1027}}) + ";\n"
    )
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef1234567890abcdef")
    monkeypatch.setattr(pub, "SITE_ROOT", site)
    monkeypatch.setattr(pub, "DATA_JS", site / "data.js")
    return db_path


class TestPublishCallSiteEmits:
    def test_publish_decision_and_act_emit_on_full_success(self, tmp_path, monkeypatch):
        db_path = _publish_env(tmp_path, monkeypatch)
        calls = {"decision": [], "act": []}
        observation_ids = []

        def deploy(host):
            return pr.DeployOutcome(host, True, f"rel-{host.role}", "")

        def emit_decision(decision):
            calls["decision"].append(decision)
            obs_id = aio_emission.build_observation(decision).knowledge_id
            observation_ids.append(obs_id)
            return {"observation_id": obs_id, "entry_ids": ["1-1"]}

        def emit_act(decision, *, causes):
            calls["act"].append((decision, causes))
            return {"actuation_id": "act-1", "entry_ids": ["1-2"]}

        rc = pr.main(
            ["--candidate-sha", "deadbeef", "--operator", "operator-test", "--db", str(db_path)],
            deployer=deploy, builder=lambda: (True, "built"),
            live_checker=lambda host, receipt: "",
            emit_decision=emit_decision, emit_act=emit_act,
        )
        assert rc == pr.EXIT_OK
        assert len(calls["decision"]) == 1
        decision = calls["decision"][0]
        assert decision["verb"] == "publish"
        assert decision["candidate_sha"] == "deadbeef"
        assert decision["operator"] == "operator-test"
        # (b) the act's causes links to the decision observation id emitted before the deploys.
        assert len(calls["act"]) == 1
        act_decision, causes = calls["act"][0]
        assert causes == observation_ids[0]
        assert act_decision["requested_action"]["outcome"] == "deployed"
        assert act_decision["requested_action"]["hosts"] == {
            "canonical": "rel-canonical", "mirror": "rel-mirror",
        }

    def test_failed_deploy_emits_the_decision_but_no_act(self, tmp_path, monkeypatch):
        """A partial publication is not a permanence act — only the decision observation emits."""
        db_path = _publish_env(tmp_path, monkeypatch)
        calls = {"decision": [], "act": []}
        deployed = []

        def failing_deploy(host):
            deployed.append(host.role)
            ok = host.role != "mirror"
            return pr.DeployOutcome(host, ok, f"rel-{host.role}" if ok else "", "" if ok else "boom")

        def emit_decision(decision):
            calls["decision"].append(decision)
            return {"observation_id": "obs-1", "entry_ids": ["1-1"]}

        def emit_act(decision, *, causes):
            calls["act"].append((decision, causes))
            return {"actuation_id": "act-1", "entry_ids": ["1-2"]}

        rc = pr.main(
            ["--candidate-sha", "deadbeef", "--operator", "operator-test", "--db", str(db_path)],
            deployer=failing_deploy, builder=lambda: (True, "built"),
            live_checker=lambda host, receipt: "",
            emit_decision=emit_decision, emit_act=emit_act,
        )
        assert rc == pr.EXIT_DEPLOY_FAILED
        assert deployed == ["canonical", "mirror"]
        assert len(calls["decision"]) == 1  # the decision was made and recorded
        assert calls["act"] == []  # ...but no act emission: the publication did not complete

    def test_publish_dry_run_emits_nothing(self, tmp_path, monkeypatch):
        """Dry-run publish is an agent plan, not a permanence decision — nothing emits."""
        db_path = _publish_env(tmp_path, monkeypatch)
        calls: list = []

        def deploy(host):
            return pr.DeployOutcome(host, True, "rel", "")

        rc = pr.main(
            ["--candidate-sha", "deadbeef", "--dry-run", "--db", str(db_path)],
            deployer=deploy, builder=lambda: (True, "built"),
            live_checker=lambda host, receipt: "",
            emit_decision=lambda d: calls.append(d) or {},
            emit_act=lambda d, **kw: calls.append(d) or {},
        )
        assert rc == pr.EXIT_OK
        assert calls == []


# ═════════════════════════════════════════════════════════════════════════════
# (d) — actuation_ingestion now has a PERMANENCE caller (the D-2 residual)
# ═════════════════════════════════════════════════════════════════════════════


def test_actuation_ingestion_has_a_permanence_caller():
    """``derive_actuation_record`` is called by the aio emission seam, which the verified
    permanence commands wire — the promote/publish/approval decisions are no longer silent.

    (Per the a0 preregistration's D-2, the "zero call sites" premise was stale — the Control
    Room steer/interrupt emit and the shadow-decision recorder predated the spec — but no
    PERMANENCE caller existed; ``aio_emission`` is that caller.)
    """
    emission_src = (ROOT / "src" / "agentic_dynamics" / "control" / "aio_emission.py").read_text(
        encoding="utf-8"
    )
    assert "derive_actuation_record" in emission_src
    assert "derive_observation_record" in emission_src
    # the permanence call sites reach the seam (they are the a5 deliverable's wiring).
    for script in ("promote.py", "publish_release.py"):
        text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "aio_emission" in text, f"{script} does not reach the aio emission seam"
    # and the seam is the callable path: build_actuation routes through the producer.
    assert aio_emission.build_actuation.__module__ == "agentic_dynamics.control.aio_emission"


def test_approval_is_a_supported_permanence_verb():
    """The seam's verb set includes approve (the AIO's approval decisions), not just promote."""
    assert "approve" in aio_emission.PERMANENCE_VERBS
    obs = aio_emission.build_observation(_decision(verb="approve", status="granted"))
    assert obs.subject_status == "approve:granted"
