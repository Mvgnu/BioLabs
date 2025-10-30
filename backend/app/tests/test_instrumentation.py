from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .conftest import TestingSessionLocal
from app import models


def _auth_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid4()}@example.com", "password": "secret"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/users/me", headers=headers)
    headers["user_id"] = me.json()["id"]
    return headers


def test_instrumentation_orchestration_flow(client):
    headers = _auth_headers(client)
    team = client.post("/api/teams/", json={"name": "Automation"}, headers=headers).json()
    equipment = client.post(
        "/api/equipment/devices",
        json={"name": "Thermocycler", "eq_type": "pcr", "team_id": team["id"]},
        headers=headers,
    ).json()

    capability = client.post(
        f"/api/instrumentation/instruments/{equipment['id']}/capabilities",
        json={
            "capability_key": "thermal.cycling",
            "title": "Thermal Cycling",
            "parameters": {"max_temp": 98},
            "guardrail_requirements": [{"id": "custody.clear", "severity": "warning"}],
        },
        headers=headers,
    )
    assert capability.status_code == 201

    sop = client.post(
        "/api/equipment/sops",
        json={"title": "PCR Run", "content": "steps", "version": 1, "team_id": team["id"]},
        headers=headers,
    ).json()
    sop_link = client.post(
        f"/api/instrumentation/instruments/{equipment['id']}/sops",
        json={"sop_id": sop["id"]},
        headers=headers,
    )
    assert sop_link.status_code == 201

    start = datetime.now(timezone.utc) + timedelta(minutes=5)
    end = start + timedelta(hours=1)
    reservation = client.post(
        f"/api/instrumentation/instruments/{equipment['id']}/reservations",
        json={
            "team_id": team["id"],
            "scheduled_start": start.isoformat(),
            "scheduled_end": end.isoformat(),
            "run_parameters": {"cycles": 30},
        },
        headers=headers,
    ).json()
    assert reservation["status"] == "scheduled"
    assert reservation["run_parameters"]["cycles"] == 30

    # overlapping reservation should be rejected
    conflict = client.post(
        f"/api/instrumentation/instruments/{equipment['id']}/reservations",
        json={
            "team_id": team["id"],
            "scheduled_start": (start + timedelta(minutes=10)).isoformat(),
            "scheduled_end": (end + timedelta(minutes=10)).isoformat(),
        },
        headers=headers,
    )
    assert conflict.status_code == 409

    dispatch = client.post(
        f"/api/instrumentation/reservations/{reservation['id']}/dispatch",
        json={"run_parameters": {"ramp_rate": 1.5}},
        headers=headers,
    ).json()
    assert dispatch["status"] == "running"
    assert dispatch["run_parameters"]["cycles"] == 30
    assert dispatch["run_parameters"]["ramp_rate"] == 1.5

    sample = client.post(
        f"/api/instrumentation/runs/{dispatch['id']}/telemetry",
        json={"channel": "temperature", "payload": {"value": 72}},
        headers=headers,
    ).json()
    assert sample["channel"] == "temperature"

    updated = client.post(
        f"/api/instrumentation/runs/{dispatch['id']}/status",
        json={"status": "completed", "guardrail_flags": []},
        headers=headers,
    ).json()
    assert updated["status"] == "completed"

    envelope = client.get(
        f"/api/instrumentation/runs/{dispatch['id']}/telemetry", headers=headers
    ).json()
    assert envelope["run"]["status"] == "completed"
    assert envelope["samples"][0]["payload"]["value"] == 72

    profiles = client.get("/api/instrumentation/instruments", headers=headers).json()
    assert profiles[0]["capabilities"]
    assert profiles[0]["sops"][0]["title"] == "PCR Run"

    # introduce a critical custody escalation to trigger guardrail blocking
    with TestingSessionLocal() as session:
        now = datetime.now(timezone.utc)
        log = models.GovernanceSampleCustodyLog(
            custody_action="hold",
            performed_at=now,
            created_at=now,
            performed_for_team_id=UUID(team["id"]),
        )
        session.add(log)
        session.flush()
        escalation = models.GovernanceCustodyEscalation(
            log_id=log.id,
            severity="critical",
            status="open",
            reason="pending custody audit",
            due_at=now + timedelta(hours=2),
            created_at=now,
            updated_at=now,
        )
        session.add(escalation)
        session.commit()

    guardrail_start = end + timedelta(hours=2)
    guardrail_end = guardrail_start + timedelta(hours=1)
    guardrail_reservation = client.post(
        f"/api/instrumentation/instruments/{equipment['id']}/reservations",
        json={
            "team_id": team["id"],
            "scheduled_start": guardrail_start.isoformat(),
            "scheduled_end": guardrail_end.isoformat(),
        },
        headers=headers,
    ).json()
    assert guardrail_reservation["status"] == "guardrail_blocked"
    assert guardrail_reservation["guardrail_snapshot"]["open_escalations"]
    assert guardrail_reservation["guardrail_snapshot"]["team_id"] == team["id"]


def test_simulation_endpoint_produces_deterministic_events(client):
    headers = _auth_headers(client)
    team = client.post("/api/teams/", json={"name": "Digital Twin"}, headers=headers).json()
    equipment = client.post(
        "/api/equipment/devices",
        json={"name": "Incubator", "eq_type": "incubator", "team_id": team["id"]},
        headers=headers,
    ).json()

    response = client.post(
        f"/api/instrumentation/instruments/{equipment['id']}/simulate",
        json={
            "scenario": "incubation_qc",
            "team_id": team["id"],
            "run_parameters": {"set_point": 42},
            "duration_minutes": 12,
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reservation"]["equipment_id"] == equipment["id"]
    assert payload["run"]["status"] == "completed"
    assert len(payload["events"]) >= 4
    assert payload["events"][0]["event_type"] == "telemetry"
    assert payload["events"][-1]["event_type"] == "status"
    assert payload["envelope"]["samples"][0]["payload"]["simulated"] is True
    assert payload["envelope"]["run"]["run_parameters"]["set_point"] == 42
