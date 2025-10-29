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
    }
    response = client.post("/api/cloning-planner/sessions", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return headers, response.json()


def test_create_cloning_planner_session_persists_inputs(client):
    _, body = _create_session(client)
    assert body["assembly_strategy"] == "gibson"
    assert body["status"] == "ready_for_finalize"
    assert body["input_sequences"][0]["metadata"]["length"] == 120
    assert isinstance(body["stage_history"], list)
    assert body["stage_history"], body["stage_history"]
    assert isinstance(body["qc_artifacts"], list)
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
        assert record.stage_history
        assert any(entry.stage == "primers" for entry in record.stage_history)
    finally:
        db.close()


def test_record_cloning_planner_stage_updates_payload(client):
    headers, body = _create_session(client)
    session_id = body["id"]

    stage_payload = {
        "payload": {"product_size_range": [90, 110], "target_tm": 62},
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
    assert updated["guardrail_state"]["primers"]["primer_state"] in {"ok", "review"}
    tags = updated["guardrail_state"]["primers"]["metadata_tags"]
    assert tags
    assert any(tag.startswith("primer_source:") for tag in tags)
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
    resume_payload = {"overrides": {"enzymes": ["EcoRI"]}}
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
