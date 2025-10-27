import uuid

from app.auth import create_access_token
from app import models
from app.tests.conftest import TestingSessionLocal


def _create_user(db, *, is_admin: bool = False) -> models.User:
    user = models.User(
        email=f"user-{uuid.uuid4()}@example.com",
        hashed_password="placeholder",
        is_admin=is_admin,
    )
    db.add(user)
    db.flush()
    return user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_baseline_lifecycle_flow(client):
    db = TestingSessionLocal()
    try:
        runner = _create_user(db)
        reviewer = _create_user(db)
        admin = _create_user(db, is_admin=True)

        template = models.ProtocolTemplate(
            name="Baseline Template",
            content="Step 1",
            created_by=admin.id,
            team_id=None,
        )
        db.add(template)
        db.flush()

        execution = models.ProtocolExecution(
            template_id=template.id,
            run_by=runner.id,
            status="completed",
            params={},
            result={},
        )
        db.add(execution)
        db.commit()
        runner_email = runner.email
        reviewer_email = reviewer.email
        admin_email = admin.email
        reviewer_id = reviewer.id
        execution_id = execution.id
        template_id = template.id
    finally:
        db.close()

    submission_payload = {
        "execution_id": str(execution_id),
        "name": "Baseline Submission",
        "description": "Initial ladder definition",
        "reviewer_ids": [str(reviewer_id)],
        "labels": [
            {"key": "environment", "value": "production"},
            {"key": "ladder", "value": "biosafety"},
        ],
    }

    submission_response = client.post(
        "/api/governance/baselines/submissions",
        json=submission_payload,
        headers=_auth_headers(runner_email),
    )
    assert submission_response.status_code == 201
    submission_body = submission_response.json()
    baseline_id = submission_body["id"]
    assert submission_body["status"] == "submitted"
    assert submission_body["labels"][0]["key"] == "environment"

    review_response = client.post(
        f"/api/governance/baselines/{baseline_id}/review",
        json={"decision": "approve", "notes": "Looks good"},
        headers=_auth_headers(reviewer_email),
    )
    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body["status"] == "approved"
    assert review_body["review_notes"] == "Looks good"

    publish_response = client.post(
        f"/api/governance/baselines/{baseline_id}/publish",
        json={"notes": "Ready for rollout"},
        headers=_auth_headers(reviewer_email),
    )
    assert publish_response.status_code == 200
    publish_body = publish_response.json()
    assert publish_body["status"] == "published"
    assert publish_body["is_current"] is True
    assert publish_body["version_number"] == 1

    list_response = client.get(
        "/api/governance/baselines",
        params={"template_id": str(template_id)},
        headers=_auth_headers(reviewer_email),
    )
    assert list_response.status_code == 200
    collection = list_response.json()
    assert collection["items"], "Expected baseline catalogue items"

    rollback_response = client.post(
        f"/api/governance/baselines/{baseline_id}/rollback",
        json={"reason": "Detected regression", "target_version_id": None},
        headers=_auth_headers(admin_email),
    )
    assert rollback_response.status_code == 200
    rollback_body = rollback_response.json()
    assert rollback_body["status"] == "rolled_back"
    assert rollback_body["is_current"] is False
    assert rollback_body["rollback_notes"] == "Detected regression"
