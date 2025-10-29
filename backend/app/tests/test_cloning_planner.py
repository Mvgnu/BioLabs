"""Tests for cloning planner API flows."""

# purpose: validate cloning planner session lifecycle operations
# status: experimental
# related_docs: docs/planning/cloning_planner_scope.md

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app import models, pubsub
from app.services import cloning_planner
from app.tests.conftest import TestingSessionLocal
from app.tests.test_template_lifecycle import admin_headers


def _create_session(client) -> tuple[str, dict]:
    headers, _ = admin_headers()
    payload = {
        "assembly_strategy": "gibson",
        "input_sequences": [
            {
                "name": "vector",
                "sequence": "ATGC" * 30,
                "metadata": {"length": 120},
            }
        ],
        "metadata": {"guardrail_state": {"state": "intake"}},
        "toolkit_preset": "multiplex",
    }
    response = client.post("/api/cloning-planner/sessions", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return headers, response.json()


def _seed_protocol_with_guardrail(user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a protocol execution with active custody backpressure."""

    db = TestingSessionLocal()
    try:
        team = models.Team(name="Ops", created_by=user_id)
        db.add(team)
        db.commit()
        db.refresh(team)
        template = models.ProtocolTemplate(
            name="Custody Protocol",
            version="1",
            content="{}",
            team_id=team.id,
            created_by=user_id,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        execution = models.ProtocolExecution(
            template_id=template.id,
            run_by=user_id,
            status="running",
            guardrail_status="halted",
            guardrail_state={
                "open_counts": {"critical": 1},
                "open_escalations": 1,
                "open_drill_count": 1,
                "qc_backpressure": True,
            },
            result={
                "custody": {
                    "open_escalations": 1,
                    "open_drill_count": 1,
                    "qc_backpressure": True,
                    "recovery_gate": True,
                    "event_overlays": {
                        "evt": {
                            "open_escalation_ids": ["esc-1"],
                            "max_severity": "critical",
                        }
                    },
                }
            },
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return team.id, execution.id
    finally:
        db.close()


def test_create_cloning_planner_session_persists_inputs(client):
    _, body = _create_session(client)
    assert body["assembly_strategy"] == "gibson"
    assert body["status"] == "ready_for_finalize"
    assert body["guardrail_gate"]["active"] is False
    assert body["input_sequences"][0]["metadata"]["length"] == 120
    assert isinstance(body["stage_history"], list)
    assert body["stage_history"], body["stage_history"]
    assert isinstance(body["qc_artifacts"], list)
    assert body["protocol_execution_id"] is None
    assert body["guardrail_state"]["toolkit"]["preset_id"] == "multiplex"
    assert body["primer_set"]["profile"]["preset_id"] == "multiplex"
    assert "multiplex_risk" in body["guardrail_state"]["primers"]
    assert body["restriction_digest"]["strategy_scores"]
    assert body["branch_state"]["branches"]
    assert body["active_branch_id"]
    assert body["stage_history"][0]["checkpoint_payload"]
    assert body["replay_window"]
    assert body["toolkit_recommendations"]["scorecard"]["preset_id"] == "multiplex"
    assert body["toolkit_recommendations"]["strategy_scores"]
    assert body["toolkit_recommendations"]["assembly"]["strategy"]
    assert "recovery_context" in body
    assert "recovery_bundle" in body
    bundle = body["recovery_bundle"]
    assert bundle["resume_token"]["session_id"] == body["id"]
    assert bundle["resume_ready"] is True
    resume_token = body["stage_history"][0]["resume_token"]
    assert resume_token["session_id"] == body["id"]
    assert body["stage_history"][0]["branch_lineage"]["history_length"] >= 1
    session_id = uuid.UUID(body["id"])

    db = TestingSessionLocal()
    try:
        record = db.get(models.CloningPlannerSession, session_id)
        assert record is not None
        assert record.assembly_strategy == "gibson"
        assert record.input_sequences[0]["name"] == "vector"
        assert record.stage_timings["intake"]["status"] == "intake_recorded"
        assert "primers" in record.stage_timings
        assert record.primer_set["summary"]["primer_count"] >= 1
        assert record.guardrail_state["toolkit"]["preset_id"] == "multiplex"
        assert record.guardrail_state["primers"]["preset_id"] == "multiplex"
        assert record.stage_history
        assert any(entry.stage == "primers" for entry in record.stage_history)
        assert record.active_branch_id
        assert record.stage_history[0].checkpoint_payload
    finally:
        db.close()


def test_record_cloning_planner_stage_updates_payload(client):
    headers, body = _create_session(client)
    session_id = body["id"]

    stage_payload = {
        "payload": {"product_size_range": [90, 110], "target_tm": 62, "preset_id": "high_gc"},
    }
    update_resp = client.post(
        f"/api/cloning-planner/sessions/{session_id}/steps/primers",
        json=stage_payload,
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["current_step"] == "restriction"
    assert updated["primer_set"]["primers"][0]["status"] == "ok"
    assert updated["guardrail_state"]["primers"]["primer_state"] in {"ok", "review", "blocked"}
    assert updated["guardrail_state"]["primers"]["preset_id"] == "high_gc"
    assert updated["guardrail_state"]["toolkit"]["preset_id"] == "high_gc"
    assert updated["primer_set"]["profile"]["preset_id"] == "high_gc"
    assert updated["toolkit_recommendations"]["scorecard"]["preset_id"] == "high_gc"
    assert updated["primer_set"]["recommendations"]["scorecard"]["preset_id"] == "high_gc"
    tags = updated["guardrail_state"]["primers"]["metadata_tags"]
    assert tags
    assert any(tag.startswith("primer_source:") for tag in tags)
    assert "multiplex_risk" in updated["guardrail_state"]["primers"]
    assert any(entry["stage"] == "primers" for entry in updated["stage_history"])
    record = next(entry for entry in updated["stage_history"] if entry["stage"] == "primers")
    assert record["resume_token"]["checkpoint"] == "primers"
    assert isinstance(record["mitigation_hints"], list)
    assert "recovery_context" in record
    assert record["recovery_bundle"]["recommended_stage"] == "primers"


def test_finalize_cloning_planner_session_sets_completion(client):
    headers, body = _create_session(client)
    session_id = body["id"]

    finalize_payload = {"guardrail_state": {"state": "ready"}}
    finalize_resp = client.post(
        f"/api/cloning-planner/sessions/{session_id}/finalize",
        json=finalize_payload,
        headers=headers,
    )
    assert finalize_resp.status_code == 200, finalize_resp.text
    data = finalize_resp.json()
    assert data["status"] == "finalized"
    assert data["guardrail_state"]["state"] == "ready"
    assert data["completed_at"] is not None

    completed_at = data["completed_at"]
    assert "T" in completed_at
    assert data["guardrail_state"]["qc"]["qc_checks"] >= 1
    assert "buffers" in data["guardrail_state"]["restriction"]
    assert "ligation_profiles" in data["guardrail_state"]["assembly"]
    assert data["guardrail_state"]["toolkit"]["preset_id"]
    assert any(entry["status"] == "finalized" for entry in data["stage_history"] if entry["stage"] == "finalize")


def test_resume_cloning_planner_session_requeues_stages(client):
    headers, body = _create_session(client)
    session_id = body["id"]

    rerun_payload = {"payload": {"product_size_range": [100, 140]}}
    rerun_resp = client.post(
        f"/api/cloning-planner/sessions/{session_id}/steps/primers",
        json=rerun_payload,
        headers=headers,
    )
    assert rerun_resp.status_code == 200, rerun_resp.text
    resume_payload = {"overrides": {"enzymes": ["EcoRI"], "preset_id": "qpcr"}}
    resume_resp = client.post(
        f"/api/cloning-planner/sessions/{session_id}/resume",
        json=resume_payload,
        headers=headers,
    )
    assert resume_resp.status_code == 200, resume_resp.text
    resumed = resume_resp.json()
    assert resumed["status"] == "ready_for_finalize"
    assert resumed["stage_timings"]["restriction"]["status"].startswith("restriction")
    assert resumed["stage_timings"]["restriction"]["task_id"]
    assert resumed["guardrail_state"]["toolkit"]["preset_id"] == "qpcr"


def test_custody_recovery_resumes_guardrail_hold(client, monkeypatch):
    headers, body = _create_session(client)
    session_id = uuid.UUID(body["id"])
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).first()
        if not user:
            user = models.User(
                email="ops@example.com",
                hashed_password="test",
                is_admin=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        _, execution_id = _seed_protocol_with_guardrail(user.id)
        planner = db.get(models.CloningPlannerSession, session_id)
        assert planner is not None
        planner.protocol_execution_id = execution_id
        timings = dict(planner.stage_timings or {})
        timings["primers"] = {
            "status": "primers_guardrail_hold",
            "hold_reason": {"gate": "custody"},
            "hold_started_at": "2024-01-01T00:00:00+00:00",
            "hold_released_at": None,
            "resumed_at": None,
            "branch_id": str(planner.active_branch_id) if planner.active_branch_id else None,
        }
        planner.stage_timings = timings
        planner.status = "primers_guardrail_hold"
        planner.current_step = "primers"
        planner.guardrail_state = {
            "custody_status": "halted",
            "custody": {"recovery_gate": True},
            "recovery": {
                "recovery_gate": True,
                "active": True,
                "active_stage": "primers",
                "holds": [],
            },
        }
        db.add(planner)
        db.commit()
        db.refresh(planner)

        resume_calls: list[dict[str, Any]] = []

        def fake_enqueue(planner_id: uuid.UUID, **kwargs):
            resume_calls.append({"planner_id": planner_id, "kwargs": kwargs})
            return "resume-task"

        monkeypatch.setattr(cloning_planner, "enqueue_pipeline", fake_enqueue)

        execution = db.get(models.ProtocolExecution, execution_id)
        assert execution is not None
        guardrail_state = dict(execution.guardrail_state or {})
        guardrail_state["recovery_gate"] = False
        execution.guardrail_state = guardrail_state
        result_payload = dict(execution.result or {})
        custody_payload = dict(result_payload.get("custody", {}))
        custody_payload["recovery_gate"] = False
        result_payload["custody"] = custody_payload
        execution.result = result_payload
        db.add(execution)
        db.commit()

        cloning_planner.propagate_custody_recovery(db, execution)
        db.refresh(planner)
        primers_entry = planner.stage_timings.get("primers") or {}

        assert resume_calls, "expected automatic resume once recovery gate cleared"
        assert primers_entry.get("hold_released_at") is not None
        assert primers_entry.get("resumed_at") is not None
        assert primers_entry.get("status") in {"primers_resuming", "primers_queued"}
        assert not (planner.guardrail_state or {}).get("recovery", {}).get("recovery_gate")
    finally:
        db.close()


def test_cloning_planner_dispatch_event_includes_branch_metadata(client, monkeypatch):
    headers, body = _create_session(client)
    session_id = uuid.UUID(body["id"])
    db = TestingSessionLocal()
    messages: list[dict[str, Any]] = []

    async def fake_publish(target_session_id: str, message: dict[str, Any]) -> None:
        messages.append(message)

    monkeypatch.setattr(pubsub, "publish_planner_event", fake_publish)

    try:
        planner = db.get(models.CloningPlannerSession, session_id)
        assert planner is not None
        event_id = "test-event"
        cloning_planner._dispatch_planner_event(
            planner,
            "stage_started",
            {"stage": "primers"},
            event_id=event_id,
        )
    finally:
        db.close()

    assert messages, "expected dispatcher to publish at least one message"
    payload = messages[0]
    assert payload["id"] == "test-event"
    assert payload["branch"]["active"] == str(body["active_branch_id"])
    assert payload["guardrail_transition"]["current"] == payload["guardrail_gate"]
    assert payload["recovery_bundle"]["resume_token"]["session_id"] == str(session_id)


def test_qc_guardrail_blocked_state_exposed(client):
    headers, body = _create_session(client)
    session_id = body["id"]

    qc_payload = {
        "payload": {
            "chromatograms": [
                {"name": "sample", "trace": [10.0, 9.8, 9.6, 9.5, 9.4]},
            ]
        }
    }
    qc_resp = client.post(
        f"/api/cloning-planner/sessions/{session_id}/steps/qc",
        json=qc_payload,
        headers=headers,
    )
    assert qc_resp.status_code == 200, qc_resp.text
    qc_data = qc_resp.json()
    assert qc_data["status"] == "qc_guardrail_blocked"
    assert qc_data["guardrail_state"]["qc"]["breaches"], qc_data["guardrail_state"]["qc"]
    assert qc_data["qc_artifacts"]
    first_artifact = qc_data["qc_artifacts"][0]
    assert first_artifact["metrics"]["signal_to_noise"] < 15
    assert first_artifact["stage_record_id"]
    assert any(entry["stage"] == "qc" for entry in qc_data["stage_history"])


def test_cancel_cloning_planner_session_marks_checkpoint(client):
    headers, body = _create_session(client)
    session_id = body["id"]

    rerun_payload = {"payload": {"target_tm": 58}}
    client.post(
        f"/api/cloning-planner/sessions/{session_id}/steps/primers",
        json=rerun_payload,
        headers=headers,
    )
    cancel_resp = client.post(
        f"/api/cloning-planner/sessions/{session_id}/cancel",
        json={"reason": "operator stopped"},
        headers=headers,
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] == "cancelled"
    assert cancel_data["stage_timings"][cancel_data["current_step"]]["status"] == "cancelled"


def test_protocol_guardrail_backpressure_blocks_pipeline(client):
    headers, user_id = admin_headers()
    _, execution_id = _seed_protocol_with_guardrail(user_id)

    payload = {
        "assembly_strategy": "gibson",
        "protocol_execution_id": str(execution_id),
        "input_sequences": [
            {
                "name": "vector",
                "sequence": "ATGC" * 20,
                "metadata": {"length": 80},
            }
        ],
    }
    resp = client.post("/api/cloning-planner/sessions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["protocol_execution_id"] == str(execution_id)
    assert data["guardrail_gate"]["active"] is True
    assert "qc_backpressure" in data["guardrail_state"].get("custody", {}) or data["guardrail_state"]["qc_backpressure"]
    primers_timing = data["stage_timings"].get("primers")
    assert primers_timing and primers_timing["status"] == "primers_guardrail_hold"

    guardrail_resp = client.get(
        f"/api/cloning-planner/sessions/{data['id']}/guardrails",
        headers=headers,
    )
    assert guardrail_resp.status_code == 200, guardrail_resp.text
    guardrail_payload = guardrail_resp.json()
    assert guardrail_payload["guardrail_gate"]["active"] is True
    custody_state = guardrail_payload["guardrail_state"].get("custody", {})
    assert custody_state.get("open_escalations") >= 1


def test_compose_recovery_bundle_handles_missing_guardrail_gate():
    """Ensure recovery bundle generation tolerates absent guardrail metadata."""

    bundle = cloning_planner._compose_recovery_bundle(
        stage="primers",
        guardrail_gate=None,
        resume_token={"session_id": "abc", "checkpoint": "primers"},
        branch_lineage={"branch_id": "branch-a", "history_length": 2},
        mitigation_hints=[{"title": "review primers", "severity": "warning"}],
        recovery_context={
            "pending_events": [
                {
                    "event_id": "evt-1",
                    "open_escalations": ["esc-1"],
                    "max_severity": "critical",
                }
            ],
            "holds": [
                {
                    "stage": "primers",
                    "status": "paused",
                    "hold_started_at": "2024-01-01T00:00:00+00:00",
                }
            ],
        },
    )

    assert bundle["resume_ready"] is True
    assert bundle["guardrail_active"] is False
    assert bundle["open_drill_count"] == 0
    assert bundle["open_escalations"] == 0
    assert bundle["guardrail_reasons"] == []
    assert bundle["custody_status"] is None
    assert bundle["pending_events"][0]["event_id"] == "evt-1"
    assert bundle["holds"][0]["stage"] == "primers"
    assert bundle["mitigation_hints"][0]["title"] == "review primers"
    assert bundle["drill_summaries"] == []


def test_compose_recovery_bundle_sanitises_malformed_guardrail_fields():
    """Guardrail counters and reasons should coerce to safe defaults."""

    bundle = cloning_planner._compose_recovery_bundle(
        stage="qc",
        guardrail_gate={
            "open_drill_count": "not-a-number",
            "open_escalations": "3",
            "active": "yes",
            "reasons": "improper-type",
            "custody_status": {"status": "halted"},
        },
        resume_token={"session_id": "xyz", "checkpoint": "qc"},
        branch_lineage=None,
        mitigation_hints=[{"title": "resolve qc"}, "ignore-me"],
        recovery_context=None,
    )

    assert bundle["open_drill_count"] == 0
    assert bundle["open_escalations"] == 3
    assert bundle["guardrail_reasons"] == []
    assert bundle["custody_status"] is None
    assert bundle["guardrail_active"] is True
    assert bundle["mitigation_hints"] == [{"title": "resolve qc"}]
    assert bundle["drill_summaries"] == []


def test_compose_recovery_bundle_marks_unresolved_drill_as_blocking_resume():
    """Open drill summaries should mark resume readiness as false."""

    bundle = cloning_planner._compose_recovery_bundle(
        stage="assembly",
        guardrail_gate={"active": False, "reasons": []},
        resume_token={"session_id": "abc", "checkpoint": "assembly"},
        branch_lineage=None,
        mitigation_hints=[],
        recovery_context={
            "drill_summaries": [
                {
                    "event_id": "evt-2",
                    "status": "open",
                    "open_escalations": ["esc-9"],
                    "mitigation_checklist": ["Resolve drill"],
                    "resume_ready": False,
                }
            ]
        },
    )

    assert bundle["resume_ready"] is False
    assert bundle["drill_summaries"] == [
        {
            "event_id": "evt-2",
            "status": "open",
            "max_severity": None,
            "open_drill_count": None,
            "open_escalations": ["esc-9"],
            "escalation_ids": [],
            "mitigation_checklist": ["Resolve drill"],
            "checklist_completed": None,
            "resume_ready": False,
            "last_updated_at": None,
        }
    ]


def test_compose_branch_comparison_flags_ahead_and_divergent_checkpoints():
    """Branch comparison summaries should expose ahead, missing, and divergent checkpoints."""

    branch_primary = uuid.uuid4()
    branch_reference = uuid.uuid4()
    planner = models.CloningPlannerSession(
        id=uuid.uuid4(),
        assembly_strategy="gibson",
        input_sequences=[],
        primer_set={},
        restriction_digest={},
        assembly_plan={},
        qc_reports={},
        inventory_reservations=[],
        guardrail_state={},
        stage_timings={},
        branch_state={
            "branches": {
                str(branch_primary): {"id": str(branch_primary), "label": "primary"},
                str(branch_reference): {"id": str(branch_reference), "label": "reference"},
            },
            "order": [str(branch_primary), str(branch_reference)],
        },
    )

    def _record(
        *,
        stage: str,
        branch_id: uuid.UUID,
        created_offset: int,
        guardrail_state: str,
    ) -> models.CloningPlannerStageRecord:
        position = f"cursor-{stage}-{created_offset}"
        checkpoint_payload = {
            "status": "completed",
            "metadata": {
                "resume_token": {"session_id": str(planner.id), "checkpoint": stage},
                "branch_lineage": {"branch_id": str(branch_id)},
                "recovery_bundle": {"resume_ready": True},
            },
        }
        now = datetime.now(timezone.utc) + timedelta(minutes=created_offset)
        return models.CloningPlannerStageRecord(
            id=uuid.uuid4(),
            session_id=planner.id,
            stage=stage,
            attempt=0,
            retry_count=0,
            status="completed",
            task_id=None,
            payload_path=None,
            payload_metadata={},
            guardrail_snapshot={},
            metrics={},
            review_state={},
            started_at=None,
            completed_at=None,
            error=None,
            branch_id=branch_id,
            checkpoint_key=stage,
            checkpoint_payload=checkpoint_payload,
            guardrail_transition={
                "current": {"state": guardrail_state, "active": guardrail_state == "halted"}
            },
            timeline_position=position,
            created_at=now,
            updated_at=now,
        )

    planner.stage_history = [
        _record(stage="intake", branch_id=branch_primary, created_offset=0, guardrail_state="ok"),
        _record(stage="primers", branch_id=branch_primary, created_offset=1, guardrail_state="ok"),
        _record(stage="assembly", branch_id=branch_primary, created_offset=2, guardrail_state="ok"),
        _record(stage="intake", branch_id=branch_reference, created_offset=0, guardrail_state="ok"),
        _record(stage="primers", branch_id=branch_reference, created_offset=1, guardrail_state="halted"),
        _record(stage="qc", branch_id=branch_reference, created_offset=3, guardrail_state="ok"),
    ]

    comparison = cloning_planner.compose_branch_comparison(
        planner,
        branch_id=str(branch_primary),
        reference_branch_id=str(branch_reference),
    )

    assert comparison["reference_branch_id"] == str(branch_reference)
    assert comparison["history_delta"] == 0
    assert any(item["stage"] == "assembly" for item in comparison["ahead_checkpoints"])
    assert any(item["stage"] == "qc" for item in comparison["missing_checkpoints"])
    assert comparison["divergent_stages"], comparison
    divergent = comparison["divergent_stages"][0]
    assert divergent["primary"]["stage"] == "primers"
    assert divergent["reference"]["guardrail_state"] == "halted"
    assert divergent["reference"]["custody_summary"]["max_severity"] == "critical"
    assert comparison["primary_custody_metrics"]["checkpoint_count"] == 3
    assert comparison["reference_custody_metrics"]["max_severity"] == "critical"
    assert comparison["custody_deltas"]["severity_delta"] < 0
    assert comparison["custody_deltas"]["open_drill_delta"] == 0


def test_compose_branch_comparison_aggregates_custody_metrics():
    """Branch comparison should aggregate custody severity and open counts."""

    branch_primary = uuid.uuid4()
    branch_reference = uuid.uuid4()
    planner = models.CloningPlannerSession(
        id=uuid.uuid4(),
        assembly_strategy="gibson",
        input_sequences=[],
        primer_set={},
        restriction_digest={},
        assembly_plan={},
        qc_reports={},
        inventory_reservations=[],
        guardrail_state={},
        stage_timings={},
        branch_state={
            "branches": {
                str(branch_primary): {"id": str(branch_primary), "label": "primary"},
                str(branch_reference): {"id": str(branch_reference), "label": "reference"},
            },
            "order": [str(branch_primary), str(branch_reference)],
        },
    )

    def _record(
        *,
        stage: str,
        branch_id: uuid.UUID,
        guardrail_state: str,
        open_drills: int,
        open_escalations: int,
        pending_events: int,
        severity: str,
        resume_ready: bool,
    ) -> models.CloningPlannerStageRecord:
        now = datetime.now(timezone.utc)
        token = {"session_id": str(planner.id), "checkpoint": stage}
        lineage = {"branch_id": str(branch_id)}
        drill_overlay = {
            "event_id": f"evt-{branch_id}-{stage}",
            "status": "open" if not resume_ready else "resolved",
            "max_severity": severity,
            "open_drill_count": open_drills,
            "open_escalations": ["esc-1"] if open_escalations else [],
            "resume_ready": resume_ready,
        }
        metadata = {
            "resume_token": token,
            "branch_lineage": lineage,
            "recovery_bundle": {
                "resume_token": token,
                "branch_lineage": lineage,
                "resume_ready": resume_ready,
                "open_drill_count": open_drills,
                "open_escalations": open_escalations,
                "pending_events": [
                    {"event_id": f"evt-{idx}", "max_severity": severity}
                    for idx in range(pending_events)
                ],
                "drill_summaries": [drill_overlay],
                "primary_hint": {"severity": severity},
            },
            "drill_summaries": [drill_overlay],
        }
        checkpoint_payload = {
            "status": "completed",
            "metadata": metadata,
        }
        return models.CloningPlannerStageRecord(
            id=uuid.uuid4(),
            session_id=planner.id,
            stage=stage,
            attempt=0,
            retry_count=0,
            status="completed",
            task_id=None,
            payload_path=None,
            payload_metadata={},
            guardrail_snapshot={},
            metrics={},
            review_state={},
            started_at=None,
            completed_at=None,
            error=None,
            branch_id=branch_id,
            checkpoint_key=stage,
            checkpoint_payload=checkpoint_payload,
            guardrail_transition={
                "current": {"state": guardrail_state, "active": guardrail_state == "halted"}
            },
            timeline_position=f"cursor-{branch_id}-{stage}",
            created_at=now,
            updated_at=now,
        )

    planner.stage_history = [
        _record(
            stage="primers",
            branch_id=branch_primary,
            guardrail_state="halted",
            open_drills=2,
            open_escalations=1,
            pending_events=2,
            severity="critical",
            resume_ready=False,
        ),
        _record(
            stage="primers",
            branch_id=branch_reference,
            guardrail_state="review",
            open_drills=0,
            open_escalations=0,
            pending_events=0,
            severity="warning",
            resume_ready=True,
        ),
    ]

    comparison = cloning_planner.compose_branch_comparison(
        planner,
        branch_id=str(branch_primary),
        reference_branch_id=str(branch_reference),
    )

    primary_metrics = comparison["primary_custody_metrics"]
    reference_metrics = comparison["reference_custody_metrics"]
    deltas = comparison["custody_deltas"]

    assert primary_metrics["open_drill_total"] == 2
    assert primary_metrics["open_escalation_total"] == 1
    assert primary_metrics["pending_event_total"] == 2
    assert primary_metrics["blocked_checkpoint_count"] == 1
    assert reference_metrics["resume_ready_count"] == 1
    assert deltas["open_drill_delta"] == 2
    assert deltas["open_escalation_delta"] == 1
    assert deltas["pending_event_delta"] == 2
    assert deltas["resume_ready_delta"] == -1
    assert deltas["severity_delta"] > 0


@pytest.mark.asyncio
async def test_planner_event_published_on_stage_update(client):
    headers, body = _create_session(client)
    session_id = body["id"]
    redis = await pubsub.get_redis()
    channel = f"planner:{session_id}"
    listener = redis.pubsub()
    await listener.subscribe(channel)
    try:
        stage_payload = {"payload": {"target_tm": 64}}
        update_resp = client.post(
            f"/api/cloning-planner/sessions/{session_id}/steps/primers",
            json=stage_payload,
            headers=headers,
        )
        assert update_resp.status_code == 200

        async def _receive_message() -> dict[str, Any]:
            while True:
                message = await listener.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    return message
                await asyncio.sleep(0.05)

        raw = await asyncio.wait_for(_receive_message(), timeout=5.0)
        assert raw["type"] == "message"
        event = json.loads(raw["data"])  # type: ignore[arg-type]
        assert event["type"] == "stage_completed"
        assert event["payload"]["stage"] == "primers"
        assert event["recovery_bundle"]["resume_token"]["checkpoint"] == "primers"
        assert isinstance(event.get("drill_summaries"), list)
    finally:
        await listener.unsubscribe(channel)
        await listener.aclose()
