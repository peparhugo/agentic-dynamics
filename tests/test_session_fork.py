"""The contemplation fan-out command: parsing, refusal, sequential receipts."""

from __future__ import annotations

from scripts.session_fork import compose, parse_prompts, run_fork_batch, session_exists


def test_parse_and_compose_blocks():
    text = "# header\n\n## First\nbody one\n\n## Second\nbody two\n"
    blocks = parse_prompts(text)
    assert [b["title"] for b in blocks] == ["First", "Second"]
    composed = compose(blocks[0]["body"])
    assert composed.startswith("CONTEMPLATION - ANALYSIS ONLY.")
    assert "TASK" in composed and "body one" in composed


def test_run_batch_is_sequential_with_receipts(tmp_path):
    calls = []

    class R:
        ok = True
        session_id = "ses_fork"
        error = ""
        total_tokens = 100
        cache_read_tokens = 80
        cache_write_tokens = 0
        cache_hit_rate = 0.8
        estimated_cost_usd = 0.001
        final_response = "answer"

    def fake(prompt, **kwargs):
        calls.append(kwargs)
        R.session_id = f"ses_fork_{len(calls)}"
        return R()

    prompts = [{"title": f"P{i}", "body": f"body {i}"} for i in range(3)]
    receipts = run_fork_batch(session_id="ses_parent", prompts=prompts, out=tmp_path,
                              model="m", timeout=10, run_agent=fake)
    assert len(receipts) == 3
    assert all(c["session_id"] == "ses_parent" and c["fork"] is True for c in calls)
    assert [r["fork_session_id"] for r in receipts] == ["ses_fork_1", "ses_fork_2", "ses_fork_3"]
    assert (tmp_path / "forks.jsonl").read_text().count("\n") == 3


def test_unknown_parent_session_refuses(tmp_path):
    import sqlite3

    db = tmp_path / "live.db"
    con = sqlite3.connect(db)
    con.execute("create table session (id text primary key)")
    con.execute("insert into session values ('ses_known')")
    con.commit()
    con.close()
    assert session_exists(db, "ses_known") is True
    assert session_exists(db, "ses_missing") is False
