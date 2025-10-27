import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.auth import create_access_token
from .conftest import TestingSessionLocal


def create_user_and_headers(email: str | None = None):
    email = email or f"{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder")
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()
    headers = {"Authorization": f"Bearer {token}"}
    return user, headers


def attach_team_membership(user: models.User) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        team = models.Team(name="Governance Team", created_by=user.id)
        db.add(team)
        db.commit()
        db.refresh(team)
        membership = models.TeamMember(team_id=team.id, user_id=user.id)
        db.add(membership)
        db.commit()
        return team.id
    finally:
        db.close()


def seed_preview_event(user: models.User, team_id: uuid.UUID | None = None) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        template = models.ProtocolTemplate(
            name="Governance Template",
            content="Stage A",
            version="1",
            team_id=team_id,
            created_by=user.id,
        )
        db.add(template)
        db.flush()

        now = datetime.now(timezone.utc)
        execution = models.ProtocolExecution(
            template_id=template.id,
            run_by=user.id,
            status="in_progress",
            result={
                "steps": {
                    "0": {
                        "status": "completed",
                        "completed_at": (now + timedelta(minutes=5)).isoformat(),
                    },
                    "1": {
                        "status": "completed",
                        "completed_at": (now + timedelta(minutes=35)).isoformat(),
                    },
                }
            },
        )
        db.add(execution)
        db.flush()

        event_payload = {
            "generated_at": now.isoformat(),
            "snapshot_id": str(uuid.uuid4()),
            "stage_count": 2,
            "blocked_stage_count": 1,
            "override_count": 1,
            "new_blocker_count": 2,
            "resolved_blocker_count": 1,
            "blocked_stage_indexes": [1],
            "stage_predictions": [
                {
                    "index": 0,
                    "projected_due_at": (now + timedelta(minutes=10)).isoformat(),
                    "mapped_step_indexes": [0],
                    "delta_status": "unchanged",
                    "delta_projected_due_minutes": -5,
                },
                {
                    "index": 1,
                    "projected_due_at": (now + timedelta(minutes=20)).isoformat(),
                    "mapped_step_indexes": [1],
                    "delta_status": "regressed",
                    "delta_projected_due_minutes": 15,
                },
            ],
        }

        event = models.ExecutionEvent(
            execution_id=execution.id,
            event_type="governance.preview.summary",
            payload=event_payload,
            actor_id=user.id,
            sequence=1,
            created_at=now,
        )
        db.add(event)
        db.commit()
        return execution.id
    finally:
        db.close()


def test_governance_analytics_sla_and_blockers(client):
    user, headers = create_user_and_headers()
    team_id = attach_team_membership(user)
    execution_id = seed_preview_event(user, team_id)

    resp = client.get("/api/governance/analytics", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["totals"]["preview_count"] == 1
    assert pytest.approx(payload["totals"]["average_blocked_ratio"], 0.001) == 0.5
    assert payload["totals"]["total_new_blockers"] == 2
    assert payload["totals"]["total_resolved_blockers"] == 1

    summary = payload["results"][0]
    assert summary["execution_id"] == str(execution_id)
    assert summary["blocked_ratio"] == 0.5
    assert summary["ladder_load"] == pytest.approx(3.0)
    assert summary["blocker_heatmap"] == [1]
    assert summary["new_blocker_count"] == 2
    assert summary["resolved_blocker_count"] == 1
    assert summary["risk_level"] == "high"
    assert summary["sla_within_target_ratio"] == pytest.approx(0.5)
    assert summary["mean_sla_delta_minutes"] == pytest.approx(5.0)

    samples = summary["sla_samples"]
    assert len(samples) == 2
    first_sample = samples[0]
    assert first_sample["stage_index"] == 0
    assert first_sample["within_target"] is True
    second_sample = samples[1]
    assert second_sample["stage_index"] == 1
    assert second_sample["within_target"] is False
    assert second_sample["delta_minutes"] == 15

    filtered = client.get(
        f"/api/governance/analytics?execution_id={execution_id}", headers=headers
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["results"]


def test_governance_analytics_rbac_denies_unauthorised_access(client):
    owner, owner_headers = create_user_and_headers()
    team_id = attach_team_membership(owner)
    execution_id = seed_preview_event(owner, team_id)

    _, outsider_headers = create_user_and_headers()
    resp = client.get(
        f"/api/governance/analytics?execution_id={execution_id}", headers=outsider_headers
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Not authorized for execution workspace"
