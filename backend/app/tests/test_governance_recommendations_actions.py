import uuid

from app import models
from app.tests.conftest import TestingSessionLocal
from .test_governance_analytics import (
    attach_team_membership,
    create_user_and_headers,
    seed_preview_event,
)


def _get_current_baseline(execution_id: uuid.UUID) -> models.GovernanceBaselineVersion:
    db = TestingSessionLocal()
    try:
        baseline = (
            db.query(models.GovernanceBaselineVersion)
            .filter(models.GovernanceBaselineVersion.execution_id == execution_id)
            .order_by(models.GovernanceBaselineVersion.created_at.desc())
            .first()
        )
        if baseline is None:
            raise AssertionError("Expected seeded execution to include baseline")
        db.refresh(baseline)
        return baseline
    finally:
        db.close()


def _create_reviewer() -> models.User:
    db = TestingSessionLocal()
    try:
        reviewer = models.User(
            email=f"reviewer-{uuid.uuid4()}@example.com",
            hashed_password="placeholder",
        )
        db.add(reviewer)
        db.commit()
        db.refresh(reviewer)
        return reviewer
    finally:
        db.close()


def test_override_reassign_execution_flow(client):
    operator, headers = create_user_and_headers()
    team_id = attach_team_membership(operator)
    execution_id = seed_preview_event(operator, team_id)
    baseline = _get_current_baseline(execution_id)
    reviewer = _create_reviewer()

    recommendation_id = f"cadence_overload:{baseline.id}"
    accept_payload = {
        "execution_id": str(execution_id),
        "action": "reassign",
        "baseline_id": str(baseline.id),
        "target_reviewer_id": str(reviewer.id),
        "notes": "Rebalancing workload",
        "metadata": {"reversible": True},
    }

    accept_response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/accept",
        headers=headers,
        json=accept_payload,
    )
    assert accept_response.status_code == 200
    accept_body = accept_response.json()
    assert accept_body["status"] == "accepted"
    assert accept_body["target_reviewer_id"] == str(reviewer.id)

    execute_payload = {
        **accept_payload,
        "metadata": {"reversible": False},
    }
    execute_response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/execute",
        headers=headers,
        json=execute_payload,
    )
    assert execute_response.status_code == 200
    execute_body = execute_response.json()
    assert execute_body["status"] == "executed"
    assert execute_body["baseline_id"] == str(baseline.id)

    db = TestingSessionLocal()
    try:
        refreshed_baseline = db.get(models.GovernanceBaselineVersion, baseline.id)
        assert refreshed_baseline is not None
        reviewer_ids = refreshed_baseline.reviewer_ids or []
        assert str(reviewer.id) in reviewer_ids

        action_rows = (
            db.query(models.GovernanceOverrideAction)
            .filter(models.GovernanceOverrideAction.recommendation_id == recommendation_id)
            .all()
        )
        assert any(row.status == "executed" for row in action_rows)

        events = (
            db.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == execution_id)
            .filter(models.ExecutionEvent.event_type == "governance.override.action")
            .all()
        )
        assert events, "Expected override action events to be logged"
    finally:
        db.close()


def test_override_execution_requires_access(client):
    operator, headers = create_user_and_headers()
    team_id = attach_team_membership(operator)
    execution_id = seed_preview_event(operator, team_id)
    baseline = _get_current_baseline(execution_id)
    reviewer = _create_reviewer()

    outsider, outsider_headers = create_user_and_headers()

    payload = {
        "execution_id": str(execution_id),
        "action": "reassign",
        "baseline_id": str(baseline.id),
        "target_reviewer_id": str(reviewer.id),
        "notes": "Attempted override",
        "metadata": {},
    }
    response = client.post(
        f"/api/governance/recommendations/override/cadence_overload:{baseline.id}/execute",
        headers=outsider_headers,
        json=payload,
    )
    assert response.status_code in {403, 404}

