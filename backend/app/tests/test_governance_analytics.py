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
        baseline_one = models.GovernanceBaselineVersion(
            execution_id=execution.id,
            template_id=template.id,
            team_id=team_id,
            name="Baseline Alpha",
            description="Initial published baseline",
            status="published",
            labels=[],
            reviewer_ids=[str(user.id)],
            version_number=1,
            is_current=False,
            submitted_by_id=user.id,
            submitted_at=now - timedelta(days=5),
            reviewed_by_id=user.id,
            reviewed_at=now - timedelta(days=5) + timedelta(hours=4),
            review_notes=None,
            published_by_id=user.id,
            published_at=now - timedelta(days=4),
            publish_notes=None,
        )
        baseline_two = models.GovernanceBaselineVersion(
            execution_id=execution.id,
            template_id=template.id,
            team_id=team_id,
            name="Baseline Beta",
            description="Current published baseline",
            status="published",
            labels=[],
            reviewer_ids=[str(user.id)],
            version_number=2,
            is_current=True,
            submitted_by_id=user.id,
            submitted_at=now - timedelta(days=2),
            reviewed_by_id=user.id,
            reviewed_at=now - timedelta(days=2) + timedelta(hours=3),
            published_by_id=user.id,
            published_at=now - timedelta(days=1),
        )
        baseline_three = models.GovernanceBaselineVersion(
            execution_id=execution.id,
            template_id=template.id,
            team_id=team_id,
            name="Baseline Gamma",
            description="Rolled back due to regression",
            status="rolled_back",
            labels=[],
            reviewer_ids=[str(user.id)],
            version_number=3,
            is_current=False,
            submitted_by_id=user.id,
            submitted_at=now - timedelta(days=1),
            reviewed_by_id=user.id,
            reviewed_at=now - timedelta(days=1) + timedelta(hours=2),
            rolled_back_by_id=user.id,
            rolled_back_at=now - timedelta(hours=12),
            rollback_notes="Detected SLA regression",
        )
        db.add_all([baseline_one, baseline_two, baseline_three])
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
    assert payload["totals"]["total_baseline_versions"] == 3
    assert payload["totals"]["total_rollbacks"] == 1
    assert payload["totals"]["average_approval_latency_minutes"] == pytest.approx(180.0)
    assert payload["totals"]["average_publication_cadence_days"] == pytest.approx(3.0)
    assert payload["totals"]["reviewer_count"] == 1
    assert payload["totals"]["streak_alert_count"] == 0
    assert payload["totals"]["reviewer_latency_p50_minutes"] == pytest.approx(
        180.0
    )
    assert payload["totals"]["reviewer_latency_p90_minutes"] == pytest.approx(
        228.0
    )
    assert payload["totals"]["reviewer_load_band_counts"] == {
        "light": 1,
        "steady": 0,
        "saturated": 0,
    }

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
    assert summary["baseline_version_count"] == 3
    assert summary["rollback_count"] == 1
    assert summary["approval_latency_minutes"] == pytest.approx(180.0)
    assert summary["publication_cadence_days"] == pytest.approx(3.0)
    assert summary["blocker_churn_index"] == pytest.approx(2.0)

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


def test_governance_analytics_override_events_adjust_metrics(client):
    user, headers = create_user_and_headers()
    team_id = attach_team_membership(user)
    execution_id = seed_preview_event(user, team_id)

    db = TestingSessionLocal()
    try:
        execution = db.get(models.ProtocolExecution, execution_id)
        assert execution is not None
        baseline = (
            db.query(models.GovernanceBaselineVersion)
            .filter(models.GovernanceBaselineVersion.execution_id == execution_id)
            .order_by(models.GovernanceBaselineVersion.version_number.asc())
            .first()
        )
        assert baseline is not None

        override_reviewer = models.User(
            email=f"override-{uuid.uuid4()}@example.com",
            hashed_password="placeholder",
        )
        db.add(override_reviewer)
        db.commit()
        db.refresh(override_reviewer)
        override_reviewer_id = override_reviewer.id
        db.add(models.TeamMember(team_id=team_id, user_id=override_reviewer_id))
        db.commit()

        now = datetime.now(timezone.utc)

        reassign_detail = {
            "recommendation_id": "cadence_overload:override",
            "baseline_id": str(baseline.id),
            "target_reviewer_id": str(override_reviewer_id),
            "changed": True,
            "reviewer_ids_before": [str(user.id)],
            "reviewer_ids_after": [str(user.id), str(override_reviewer_id)],
            "execution_hash": "hash-reassign",
            "reversible": True,
        }
        reassign_event = models.ExecutionEvent(
            execution_id=execution.id,
            event_type="governance.override.action",
            payload={
                "recommendation_id": reassign_detail["recommendation_id"],
                "rule_key": "cadence_overload",
                "action": "reassign",
                "status": "executed",
                "actor_id": str(user.id),
                "detail": reassign_detail,
            },
            actor_id=user.id,
            sequence=2,
            created_at=now + timedelta(minutes=1),
        )
        cooldown_detail = {
            "recommendation_id": "streak_cooldown:override",
            "cooldown_minutes": 30,
            "notes": "grant rest window",
            "baseline_id": str(baseline.id),
            "execution_hash": "hash-cooldown",
        }
        cooldown_event = models.ExecutionEvent(
            execution_id=execution.id,
            event_type="governance.override.action",
            payload={
                "recommendation_id": cooldown_detail["recommendation_id"],
                "rule_key": "streak_cooldown",
                "action": "cooldown",
                "status": "executed",
                "actor_id": str(user.id),
                "detail": cooldown_detail,
            },
            actor_id=user.id,
            sequence=3,
            created_at=now + timedelta(minutes=2),
        )
        db.add_all([reassign_event, cooldown_event])
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/governance/analytics", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()

    summary = payload["results"][0]
    assert summary["override_actions_executed"] == 2
    assert summary["override_actions_reversed"] == 0
    assert summary["override_cooldown_minutes"] == pytest.approx(30.0)
    assert summary["sla_within_target_ratio"] == pytest.approx(2 / 3, rel=1e-3)
    assert summary["mean_sla_delta_minutes"] == pytest.approx(-20 / 3, rel=1e-3)

    totals = payload["totals"]
    assert totals["reviewer_count"] == 2

    reviewer_ids = {reviewer["reviewer_id"] for reviewer in payload["reviewer_cadence"]}
    assert str(override_reviewer_id) in reviewer_ids


def test_governance_analytics_reviewer_view(client):
    user, headers = create_user_and_headers()
    team_id = attach_team_membership(user)
    seed_preview_event(user, team_id)

    resp = client.get(
        "/api/governance/analytics",
        headers=headers,
        params={"view": "reviewer"},
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert "results" not in payload
    assert payload["totals"]["reviewer_count"] == 1
    assert payload["totals"]["load_band_counts"]["light"] == 1
    assert payload["totals"]["reviewer_latency_p50_minutes"] == pytest.approx(180.0)
    assert payload["totals"]["reviewer_latency_p90_minutes"] == pytest.approx(228.0)
    assert payload["totals"]["streak_alert_count"] == 0
    reviewer = payload["reviewers"][0]
    assert reviewer["reviewer_id"] == str(user.id)
    assert reviewer["load_band"] == "light"

    assert reviewer["latency_bands"][1]["label"] == "two_to_eight_h"
    assert reviewer["latency_bands"][1]["count"] == 3


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
