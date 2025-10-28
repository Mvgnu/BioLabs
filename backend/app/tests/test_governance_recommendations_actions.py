import uuid
from datetime import datetime, timezone

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
    lineage_payload = {
        "scenario_id": str(uuid.uuid4()),
        "metadata": {"source": "test"},
    }
    accept_payload = {
        "execution_id": str(execution_id),
        "action": "reassign",
        "baseline_id": str(baseline.id),
        "target_reviewer_id": str(reviewer.id),
        "notes": "Rebalancing workload",
        "metadata": {"reversible": True},
        "lineage": lineage_payload,
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

    execute_payload = {**accept_payload, "metadata": {"reversible": False}}
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


def test_override_execute_is_idempotent(client):
    operator, headers = create_user_and_headers()
    team_id = attach_team_membership(operator)
    execution_id = seed_preview_event(operator, team_id)
    baseline = _get_current_baseline(execution_id)
    reviewer = _create_reviewer()

    recommendation_id = f"cadence_overload:{baseline.id}"
    lineage_payload = {
        "scenario_id": str(uuid.uuid4()),
        "metadata": {"source": "test"},
    }
    payload = {
        "execution_id": str(execution_id),
        "action": "reassign",
        "baseline_id": str(baseline.id),
        "target_reviewer_id": str(reviewer.id),
        "notes": "Primary execution",
        "metadata": {"reversible": True},
        "lineage": lineage_payload,
    }

    first_response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/execute",
        headers=headers,
        json=payload,
    )
    assert first_response.status_code == 200
    first_body = first_response.json()
    assert first_body["status"] == "executed"

    second_response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/execute",
        headers=headers,
        json=payload,
    )
    assert second_response.status_code == 200
    second_body = second_response.json()
    assert second_body["id"] == first_body["id"]
    assert second_body["status"] == "executed"

    db = TestingSessionLocal()
    try:
        refreshed_baseline = db.get(models.GovernanceBaselineVersion, baseline.id)
        assert refreshed_baseline is not None
        reviewer_ids = refreshed_baseline.reviewer_ids or []
        assert reviewer_ids.count(str(reviewer.id)) == 1

        events = (
            db.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == execution_id)
            .filter(models.ExecutionEvent.event_type == "governance.override.action")
            .all()
        )
        assert len(events) == 1, "Idempotent execution should emit a single event"
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
        "lineage": {
            "scenario_id": str(uuid.uuid4()),
            "metadata": {"source": "test"},
        },
    }
    response = client.post(
        f"/api/governance/recommendations/override/cadence_overload:{baseline.id}/execute",
        headers=outsider_headers,
        json=payload,
    )
    assert response.status_code in {403, 404}


def test_override_reversal_flow(client):
    operator, headers = create_user_and_headers()
    team_id = attach_team_membership(operator)
    execution_id = seed_preview_event(operator, team_id)
    baseline = _get_current_baseline(execution_id)
    reviewer = _create_reviewer()

    recommendation_id = f"cadence_overload:{baseline.id}"
    lineage_payload = {
        "scenario_id": str(uuid.uuid4()),
        "metadata": {"source": "test"},
    }
    execute_payload = {
        "execution_id": str(execution_id),
        "action": "reassign",
        "baseline_id": str(baseline.id),
        "target_reviewer_id": str(reviewer.id),
        "notes": "Applying override",
        "metadata": {"reversible": True},
        "lineage": lineage_payload,
    }

    execute_response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/execute",
        headers=headers,
        json=execute_payload,
    )
    assert execute_response.status_code == 200
    execute_body = execute_response.json()
    assert execute_body["status"] == "executed"

    reversal_payload = {
        "execution_id": str(execution_id),
        "baseline_id": str(baseline.id),
        "notes": "Undo override",
        "metadata": {"reason": "operator_request", "cooldown_minutes": 30},
    }
    reverse_response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/reverse",
        headers=headers,
        json=reversal_payload,
    )
    assert reverse_response.status_code == 200
    reverse_body = reverse_response.json()
    assert reverse_body["status"] == "reversed"
    assert reverse_body["baseline_id"] == str(baseline.id)
    assert reverse_body["target_reviewer_id"] == str(reviewer.id)
    assert reverse_body.get("cooldown_expires_at") is not None
    assert reverse_body.get("cooldown_window_minutes") == 30
    assert reverse_body.get("reversal_event", {}).get("diffs"), "Reversal diff should be populated"

    repeat_reverse = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/reverse",
        headers=headers,
        json=reversal_payload,
    )
    assert repeat_reverse.status_code == 400
    assert "cooling down" in repeat_reverse.json()["detail"]

    db = TestingSessionLocal()
    try:
        refreshed_baseline = db.get(models.GovernanceBaselineVersion, baseline.id)
        assert refreshed_baseline is not None
        reviewer_ids = refreshed_baseline.reviewer_ids or []
        assert str(reviewer.id) not in reviewer_ids

        events = (
            db.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == execution_id)
            .filter(models.ExecutionEvent.event_type == "governance.override.action")
            .order_by(models.ExecutionEvent.created_at.asc())
            .all()
        )
        assert len(events) == 2, "Execute and reverse should emit two events"
        payloads = [event.payload for event in events]
        assert payloads[-1].get("status") == "reversed"
        assert payloads[-1].get("detail", {}).get("reversal") is True
    finally:
        db.close()


def test_override_reversal_respects_active_lock(client):
    operator, headers = create_user_and_headers()
    team_id = attach_team_membership(operator)
    execution_id = seed_preview_event(operator, team_id)
    baseline = _get_current_baseline(execution_id)
    reviewer = _create_reviewer()

    recommendation_id = f"cadence_overload:{baseline.id}"
    lineage_payload = {
        "scenario_id": str(uuid.uuid4()),
        "metadata": {"source": "test"},
    }
    execute_payload = {
        "execution_id": str(execution_id),
        "action": "reassign",
        "baseline_id": str(baseline.id),
        "target_reviewer_id": str(reviewer.id),
        "notes": "Applying override",
        "metadata": {"reversible": True},
        "lineage": lineage_payload,
    }

    execute_response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/execute",
        headers=headers,
        json=execute_payload,
    )
    assert execute_response.status_code == 200

    db = TestingSessionLocal()
    try:
        record = (
            db.query(models.GovernanceOverrideAction)
            .filter(models.GovernanceOverrideAction.recommendation_id == recommendation_id)
            .one()
        )
        record.reversal_lock_token = "locked"
        record.reversal_lock_acquired_at = datetime.now(timezone.utc)
        record.reversal_lock_actor_id = operator.id
        db.add(record)
        db.commit()
    finally:
        db.close()

    reversal_payload = {
        "execution_id": str(execution_id),
        "baseline_id": str(baseline.id),
        "notes": "Undo override",
        "metadata": {"reason": "operator_request", "cooldown_minutes": 15},
    }
    response = client.post(
        f"/api/governance/recommendations/override/{recommendation_id}/reverse",
        headers=headers,
        json=reversal_payload,
    )
    assert response.status_code == 400
    assert "already being processed" in response.json()["detail"]

