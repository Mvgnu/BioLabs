import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.auth import create_access_token
from app.recommendations.timeline import load_governance_decision_timeline

from .conftest import TestingSessionLocal


def create_user(email: str | None = None, is_admin: bool = False) -> models.User:
    db = TestingSessionLocal()
    try:
        user = models.User(
            email=email or f"{uuid.uuid4()}@example.com",
            hashed_password="placeholder",
            is_admin=is_admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def create_auth_headers(user: models.User) -> dict[str, str]:
    token = create_access_token({"sub": user.email})
    return {"Authorization": f"Bearer {token}"}


def ensure_team_membership(user: models.User) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        team = models.Team(name="Governance", created_by=user.id)
        db.add(team)
        db.flush()
        db.add(models.TeamMember(team_id=team.id, user_id=user.id))
        db.commit()
        return team.id
    finally:
        db.close()


def seed_governance_artifacts(
    actor: models.User,
    team_id: uuid.UUID | None = None,
    *,
    include_override: bool = True,
) -> tuple[uuid.UUID, uuid.UUID]:
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    try:
        template = models.ProtocolTemplate(
            name="Governance Template",
            content="{}",
            version="1",
            team_id=team_id,
            created_by=actor.id,
        )
        db.add(template)
        db.flush()

        execution = models.ProtocolExecution(
            template_id=template.id,
            run_by=actor.id,
            status="in_progress",
        )
        db.add(execution)
        db.flush()

        baseline = models.GovernanceBaselineVersion(
            execution_id=execution.id,
            template_id=template.id,
            team_id=team_id,
            name="Baseline", 
            description="",
            status="published",
            labels=[],
            reviewer_ids=[str(actor.id)],
            version_number=1,
            is_current=True,
            submitted_by_id=actor.id,
            submitted_at=now - timedelta(days=2),
            reviewed_by_id=actor.id,
            reviewed_at=now - timedelta(days=2) + timedelta(hours=4),
            published_by_id=actor.id,
            published_at=now - timedelta(days=1, hours=12),
        )
        db.add(baseline)
        db.flush()

        db.add(
            models.GovernanceBaselineEvent(
                baseline_id=baseline.id,
                action="approved",
                detail={"notes": "Approved baseline"},
                performed_by_id=actor.id,
                created_at=now - timedelta(hours=20),
            )
        )

        preview_payload = {
            "generated_at": now.isoformat(),
            "stage_count": 1,
            "blocked_stage_count": 0,
            "override_count": 0,
            "new_blocker_count": 0,
            "resolved_blocker_count": 0,
            "stage_predictions": [],
        }
        db.add(
            models.ExecutionEvent(
                execution_id=execution.id,
                event_type="governance.preview.summary",
                payload=preview_payload,
                actor_id=actor.id,
                sequence=1,
                created_at=now - timedelta(hours=21),
            )
        )

        if include_override:
            db.add(
                models.ExecutionEvent(
                    execution_id=execution.id,
                    event_type="governance.recommendation.override",
                    payload={
                        "rule_key": "cadence_overload",
                        "recommendation": {"priority": "high"},
                        "summary": "Reassign reviewer",
                    },
                    actor_id=actor.id,
                    sequence=2,
                    created_at=now - timedelta(hours=19),
                )
            )
            db.add(
                models.ExecutionEvent(
                    execution_id=execution.id,
                    event_type="governance.override.action",
                    payload={
                        "rule_key": "cadence_overload",
                        "action": "reassign",
                        "status": "accepted",
                        "summary": "Override executed",
                    },
                    actor_id=actor.id,
                    sequence=3,
                    created_at=now - timedelta(hours=18),
                )
            )

        db.commit()
        return execution.id, baseline.id
    finally:
        db.close()


@pytest.mark.usefixtures("client")
def test_load_governance_decision_timeline_blends_sources():
    user = create_user()
    team_id = ensure_team_membership(user)
    execution_id, _ = seed_governance_artifacts(user, team_id=team_id)

    db = TestingSessionLocal()
    try:
        page = load_governance_decision_timeline(
            db,
            user,
            membership_ids={team_id},
            execution_ids=[execution_id],
            limit=10,
        )
    finally:
        db.close()

    entry_types = {entry.entry_type for entry in page.entries}
    assert {"baseline_event", "override_recommendation", "override_action", "analytics_snapshot"}.issubset(entry_types)


@pytest.mark.usefixtures("client")
def test_governance_timeline_respects_team_membership():
    owner = create_user()
    team_one = ensure_team_membership(owner)
    execution_a, _ = seed_governance_artifacts(owner, team_id=team_one)

    outsider = create_user()
    team_two = ensure_team_membership(outsider)
    seed_governance_artifacts(outsider, team_id=team_two)

    db = TestingSessionLocal()
    try:
        page = load_governance_decision_timeline(
            db,
            owner,
            membership_ids={team_one},
            execution_ids=[execution_a],
            limit=10,
        )
    finally:
        db.close()

    for entry in page.entries:
        assert entry.execution_id == execution_a or entry.entry_type == "analytics_snapshot"


def test_governance_timeline_endpoint_returns_feed(client):
    user = create_user()
    team_id = ensure_team_membership(user)
    execution_id, _ = seed_governance_artifacts(user, team_id=team_id)
    headers = create_auth_headers(user)

    response = client.get(
        "/api/experiment-console/governance/timeline",
        headers=headers,
        params={"execution_id": str(execution_id)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "entries" in payload
    assert payload["entries"]
    assert any(entry["entry_type"] == "baseline_event" for entry in payload["entries"])
