"""Tests for cloning planner API flows."""

# purpose: validate cloning planner session lifecycle operations
# status: experimental
# related_docs: docs/planning/cloning_planner_scope.md

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from typing import Any

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
    tags = updated["guardrail_state"]["primers"]["metadata_tags"]
    assert tags
    assert any(tag.startswith("primer_source:") for tag in tags)
    assert "multiplex_risk" in updated["guardrail_state"]["primers"]
    assert any(entry["stage"] == "primers" for entry in updated["stage_history"])


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
    finally:
        await listener.unsubscribe(channel)
        await listener.aclose()
