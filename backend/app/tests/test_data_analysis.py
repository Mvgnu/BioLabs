import uuid
from datetime import datetime, timezone

from .conftest import TestingSessionLocal
from .. import models
from app.auth import create_access_token


def get_headers(client):
    email = f"data{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder")
        db.add(user)
        db.commit()
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def test_csv_summary(client):
    headers = get_headers(client)
    csv = b"a,b\n1,2\n3,4\n"
    resp = client.post(
        "/api/data/summary",
        files={"upload": ("test.csv", csv, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["a"]["mean"] == 2.0
    assert data["b"]["mean"] == 3.0


def test_data_evidence_domains(client):
    headers = get_headers(client)
    template = client.post(
        "/api/protocols/templates",
        json={"name": "Analytics Template", "content": "Steps"},
        headers=headers,
    ).json()
    session = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Run"},
        headers=headers,
    ).json()
    execution_id = session["execution"]["id"]

    db = TestingSessionLocal()
    try:
        exec_uuid = uuid.UUID(execution_id)
        now = datetime.now(timezone.utc)
        events = [
            models.ExecutionEvent(
                execution_id=exec_uuid,
                event_type="analytics.snapshot.primary",
                payload={"label": "Primary Snapshot", "metrics": {"yield": {"value": 0.92}}},
                actor_id=None,
                sequence=100,
                created_at=now,
            ),
            models.ExecutionEvent(
                execution_id=exec_uuid,
                event_type="qc.metric.instrument",
                payload={
                    "label": "QC Readings",
                    "readings": [
                        {"name": "pH", "value": 7.1},
                        {"name": "pH", "value": 7.3},
                    ],
                },
                actor_id=None,
                sequence=101,
                created_at=now,
            ),
            models.ExecutionEvent(
                execution_id=exec_uuid,
                event_type="remediation.report.actions",
                payload={"label": "Remediation", "actions": ["inventory:restore:1"]},
                actor_id=None,
                sequence=102,
                created_at=now,
            ),
        ]
        db.add_all(events)
        db.commit()
    finally:
        db.close()

    analytics_page = client.get("/api/data/evidence", headers=headers)
    assert analytics_page.status_code == 200
    analytics_data = analytics_page.json()
    assert any(item["type"] == "analytics_snapshot" for item in analytics_data["items"])

    qc_page = client.get(
        "/api/data/evidence",
        params={"domain": "qc_metric"},
        headers=headers,
    )
    assert qc_page.status_code == 200
    qc_data = qc_page.json()
    assert any(item["type"] == "qc_metric" for item in qc_data["items"])

    remediation_page = client.get(
        "/api/data/evidence",
        params={"domain": "remediation_report"},
        headers=headers,
    )
    assert remediation_page.status_code == 200
    remediation_data = remediation_page.json()
    assert any(item["type"] == "remediation_report" for item in remediation_data["items"])
