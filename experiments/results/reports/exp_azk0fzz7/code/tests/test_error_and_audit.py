import os


def test_404_json(client):
    res = client.get("/nope")
    assert res.status_code == 404
    assert res.get_json()["error"] == "not_found"


def test_audit_log_written(client):
    # Trigger a simple request which should be logged
    res = client.get("/healthz")
    assert res.status_code == 200

    # Audit log should exist and contain a line with path /healthz
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "audit.log"))
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        content = f.read()
    assert "/healthz" in content
