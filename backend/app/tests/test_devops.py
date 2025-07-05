from .conftest import client
from app.tasks import backup_database
import os


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"request_count" in resp.content


def test_backup_database(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    path = backup_database()
    assert os.path.exists(path)
