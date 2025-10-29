from datetime import datetime, timezone
from uuid import uuid4

from app import auth, models
from app.tests.conftest import TestingSessionLocal


def _register_user(email: str) -> str:
    session = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="test", is_admin=False)
        session.add(user)
        session.commit()
    finally:
        session.close()
    return auth.create_access_token({"sub": email})


def _resolve_user(email: str) -> models.User:
    session = TestingSessionLocal()
    try:
        user = session.query(models.User).filter_by(email=email).first()
        assert user is not None
        session.expunge(user)
        return user
    finally:
        session.close()


def test_lifecycle_timeline_combines_planner_history(client):
    owner_token = _register_user("planner-owner@example.com")
    owner = _resolve_user("planner-owner@example.com")

    session_id = uuid4()
    stage_id = uuid4()
    db = TestingSessionLocal()
    try:
        planner = models.CloningPlannerSession(
            id=session_id,
            created_by_id=owner.id,
            assembly_strategy="golden_gate",
            input_sequences=[],
            primer_set={},
            restriction_digest={},
            assembly_plan={},
            qc_reports={},
            inventory_reservations=[],
            guardrail_state={},
            stage_timings={},
            branch_state={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(planner)
        record = models.CloningPlannerStageRecord(
            id=stage_id,
            session_id=session_id,
            stage="primers",
            status="completed",
            attempt=0,
            retry_count=0,
            payload_metadata={},
            guardrail_snapshot={"flags": ["tm_range"]},
            metrics={},
            review_state={},
            checkpoint_key="primers",
            checkpoint_payload={"resume_token": {"checkpoint": "primers"}},
            guardrail_transition={"summary": "Primers verified"},
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/lifecycle/timeline",
        params={"planner_session_id": str(session_id)},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["total_events"] == 1
    assert payload["entries"], "Expected lifecycle entries"
    entry = payload["entries"][0]
    assert entry["entry_id"].startswith("planner:")
    assert entry["metadata"]["checkpoint_key"] == "primers"


def test_lifecycle_scope_enforces_access_controls(client):
    owner_token = _register_user("owner@example.com")
    other_token = _register_user("other@example.com")
    owner = _resolve_user("owner@example.com")

    session_id = uuid4()
    db = TestingSessionLocal()
    try:
        planner = models.CloningPlannerSession(
            id=session_id,
            created_by_id=owner.id,
            assembly_strategy="gibson",
            input_sequences=[],
            primer_set={},
            restriction_digest={},
            assembly_plan={},
            qc_reports={},
            inventory_reservations=[],
            guardrail_state={},
            stage_timings={},
            branch_state={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(planner)
        db.commit()
    finally:
        db.close()

    forbidden = client.get(
        "/api/lifecycle/timeline",
        params={"planner_session_id": str(session_id)},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        "/api/lifecycle/timeline",
        params={"planner_session_id": str(session_id)},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert allowed.status_code == 200

