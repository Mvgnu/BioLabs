from uuid import uuid4

from fastapi.testclient import TestClient

from app import models
from app.auth import create_access_token
from app.tests.conftest import TestingSessionLocal


def _register_user(client: TestClient) -> tuple[str, dict[str, str]]:
    del client  # API not used; keep signature consistent with other helpers
    email = f"governance-tester-{uuid4()}@example.com"
    session = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder")
        session.add(user)
        session.commit()
    finally:
        session.close()
    token = create_access_token({"sub": email})
    return email, {"Authorization": f"Bearer {token}"}


def test_notebook_export_requires_guardrails(client: TestClient) -> None:
    email, headers = _register_user(client)

    session = TestingSessionLocal()
    try:
        user = session.query(models.User).filter(models.User.email == email).one()
        template = models.ProtocolTemplate(
            name="Guardrail Template",
            content="# stage\n",
            version="1",
            created_by=user.id,
        )
        session.add(template)
        session.flush()

        execution = models.ProtocolExecution(
            template_id=template.id,
            run_by=user.id,
            status="in_progress",
        )
        session.add(execution)
        session.flush()

        entry = models.NotebookEntry(
            title="Lab note",
            content="Observation",
            execution_id=execution.id,
            created_by=user.id,
        )
        session.add(entry)
        session.commit()
        entry_id = str(entry.id)
        execution_id = execution.id
    finally:
        session.close()

    resp = client.get(f"/api/notebook/entries/{entry_id}/export", headers=headers)
    assert resp.status_code == 409
    assert "narrative packaging guardrails" in resp.json()["detail"]

    session = TestingSessionLocal()
    try:
        events = (
            session.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == execution_id)
            .filter(
                models.ExecutionEvent.event_type
                == "notebook_export.guardrail_blocked"
            )
            .all()
        )
        assert events, "guardrail block should be recorded as execution event"
    finally:
        session.close()


def test_inventory_export_disabled_without_packaging(client: TestClient) -> None:
    _, headers = _register_user(client)

    resp = client.get("/api/inventory/export", headers=headers)
    assert resp.status_code == 409
    assert "Inventory exports now require DNA asset governance packaging" in resp.json()[
        "detail"
    ]
