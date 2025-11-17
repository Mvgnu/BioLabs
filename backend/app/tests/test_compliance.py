import uuid

from app import models

from .conftest import TestingSessionLocal, client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_enterprise_compliance_workflow(client):
    headers = get_headers(client)
    org_payload = {
        "name": "Helios Labs",
        "slug": "helios",
        "primary_region": "us-east-1",
        "allowed_regions": ["us-east-1", "us-west-2"],
        "encryption_policy": {"at_rest": "kms", "in_transit": "tls1.3"},
        "retention_policy": {"dna_asset": {"days": 730}},
    }
    org_resp = client.post("/api/compliance/organizations", json=org_payload, headers=headers)
    assert org_resp.status_code == 201
    organization_id = org_resp.json()["id"]

    policy_payload = {
        "data_domain": "dna_asset",
        "allowed_regions": ["us-east-1"],
        "default_region": "us-east-1",
        "encryption_at_rest": "kms",
        "encryption_in_transit": "tls1.3",
        "retention_days": 365,
        "audit_interval_days": 30,
        "guardrail_flags": ["encryption:strict"],
    }
    policy_resp = client.post(
        f"/api/compliance/organizations/{organization_id}/policies",
        json=policy_payload,
        headers=headers,
    )
    assert policy_resp.status_code == 201
    assert policy_resp.json()["guardrail_flags"] == ["encryption:strict"]

    hold_resp = client.post(
        f"/api/compliance/organizations/{organization_id}/legal-holds",
        json={"scope_type": "dna_asset", "scope_reference": "asset-1", "reason": "investigation"},
        headers=headers,
    )
    assert hold_resp.status_code == 201
    hold_id = hold_resp.json()["id"]

    release_resp = client.post(
        f"/api/compliance/legal-holds/{hold_id}/release",
        json={"scope_type": "dna_asset", "scope_reference": "asset-1", "reason": "complete"},
        headers=headers,
    )
    assert release_resp.status_code == 200
    assert release_resp.json()["status"] == "released"

    report_resp = client.get("/api/compliance/reports/export", headers=headers)
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["organizations"][0]["policy_count"] == 1

    record_payload = {
        "record_type": "guardrail",
        "data_domain": "dna_asset",
        "organization_id": organization_id,
        "status": "pending",
        "region": "us-east-1",
        "notes": "Residency verified",
    }
    record_resp = client.post("/api/compliance/records", json=record_payload, headers=headers)
    assert record_resp.status_code == 201
    record_body = record_resp.json()
    assert "encryption:strict" in record_body.get("guardrail_flags", [])
    assert record_body["retention_period_days"] == 365

    record_id = record_body["id"]
    update_resp = client.put(
        f"/api/compliance/records/{record_id}",
        json={"region": "eu-west-1", "status": "restricted"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert "residency:region_blocked" in update_resp.json()["guardrail_flags"]

    session = TestingSessionLocal()
    try:
        stored = (
            session.query(models.ComplianceRecord)
            .filter(models.ComplianceRecord.id == uuid.UUID(record_id))
            .one()
        )
        assert "encryption:strict" in (stored.guardrail_flags or [])
    finally:
        session.close()

    records_resp = client.get("/api/compliance/records", headers=headers)
    assert records_resp.status_code == 200
    assert len(records_resp.json()) == 1

    summary_resp = client.get("/api/compliance/summary", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    statuses = {row["status"]: row["count"] for row in summary}
    assert statuses.get("restricted") == 1
