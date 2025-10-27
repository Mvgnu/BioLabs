import uuid
from datetime import datetime, timedelta, timezone

from app import models, schemas
from app.recommendations.governance import generate_override_recommendations
from .conftest import TestingSessionLocal
from .test_governance_analytics import (
    attach_team_membership,
    create_user_and_headers,
    seed_preview_event,
)


def test_generate_override_recommendations_rules(monkeypatch):
    db = TestingSessionLocal()
    try:
        user = models.User(email="governance@example.com", hashed_password="pw")
        db.add(user)
        db.commit()
        db.refresh(user)

        template = models.ProtocolTemplate(
            name="Test Governance Template",
            content="Stage",
            version="1",
            created_by=user.id,
        )
        db.add(template)
        db.flush()

        execution = models.ProtocolExecution(
            template_id=template.id,
            run_by=user.id,
            status="completed",
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        reviewer_id = uuid.uuid4()
        reviewer_summary = schemas.build_reviewer_cadence_summary(
            reviewer_id=reviewer_id,
            reviewer_email="reviewer@example.com",
            reviewer_name="Cadence Reviewer",
            assignment_count=14,
            completion_count=12,
            pending_count=3,
            load_band="saturated",
            average_latency_minutes=300.0,
            latency_p50_minutes=280.0,
            latency_p90_minutes=420.0,
            latency_bands=[],
            blocked_ratio_trailing=0.7,
            churn_signal=3.5,
            rollback_precursor_count=2,
            publish_streak=4,
            last_publish_at=datetime.now(timezone.utc) - timedelta(hours=2),
            streak_alert=True,
        )

        analytics_report = schemas.GovernanceAnalyticsReport(
            results=[],
            reviewer_cadence=[reviewer_summary],
            totals=schemas.GovernanceAnalyticsTotals(
                preview_count=0,
                average_blocked_ratio=0.0,
                total_new_blockers=0,
                total_resolved_blockers=0,
                average_sla_within_target_ratio=None,
                total_baseline_versions=0,
                total_rollbacks=0,
                average_approval_latency_minutes=None,
                average_publication_cadence_days=None,
                reviewer_count=1,
                streak_alert_count=1,
                reviewer_latency_p50_minutes=120.0,
                reviewer_latency_p90_minutes=360.0,
                reviewer_load_band_counts=schemas.build_reviewer_load_band_counts(
                    saturated=1
                ),
            ),
        )

        monkeypatch.setattr(
            "app.recommendations.governance.compute_governance_analytics",
            lambda *args, **kwargs: analytics_report,
        )

        report = generate_override_recommendations(
            db,
            user,
            team_ids=[],
            execution_ids=[execution.id],
            limit=10,
        )

        assert len(report.recommendations) == 3
        actions = {rec.action for rec in report.recommendations}
        assert actions == {"reassign", "cooldown", "escalate"}
        for recommendation in report.recommendations:
            assert recommendation.reviewer_id == reviewer_id
            assert execution.id in recommendation.related_execution_ids

        events = (
            db.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == execution.id)
            .filter(models.ExecutionEvent.event_type == "governance.recommendation.override")
            .all()
        )
        assert len(events) == 3
    finally:
        db.close()


def test_override_recommendations_requires_access(client):
    owner, owner_headers = create_user_and_headers()
    team_id = attach_team_membership(owner)
    execution_id = seed_preview_event(owner, team_id)

    other_user, other_headers = create_user_and_headers()

    response = client.get(
        "/api/governance/recommendations/override",
        headers=other_headers,
        params={"execution_id": str(execution_id)},
    )
    assert response.status_code in {403, 404}

    permitted_response = client.get(
        "/api/governance/recommendations/override",
        headers=owner_headers,
        params={"execution_id": str(execution_id)},
    )
    assert permitted_response.status_code == 200
    payload = permitted_response.json()
    assert "recommendations" in payload
