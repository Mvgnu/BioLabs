import uuid

import pytest

from app.main import app
from app import models
from app.auth import get_current_user

from app.tests.conftest import TestingSessionLocal


@pytest.fixture
def auth_headers():
    session = TestingSessionLocal()
    user = models.User(
        id=uuid.uuid4(),
        email=f"dna-tester-{uuid.uuid4()}@example.com",
        hashed_password="test",
        is_admin=True,
        is_active=True,
    )
    session.add(user)
    session.commit()

    def override_user() -> models.User:
        return user

    app.dependency_overrides[get_current_user] = override_user
    try:
        yield {}, user
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        session.close()


def test_create_and_list_assets(client, auth_headers):
    headers, user = auth_headers
    payload = {
        "name": "Test Plasmid",
        "sequence": "ATGC" * 25,
        "metadata": {"source": "unit-test"},
        "tags": ["plasmid", "draft"],
        "annotations": [
            {"label": "feature", "feature_type": "CDS", "start": 1, "end": 20},
        ],
    }
    resp = client.post("/api/dna-assets", json=payload, headers=headers)
    assert resp.status_code == 201
    asset = resp.json()
    assert asset["name"] == "Test Plasmid"
    assert sorted(asset["tags"]) == ["draft", "plasmid"]
    latest = asset["latest_version"]
    assert latest["sequence_length"] == 100
    assert latest["gc_content"] > 0
    kinetics_summary = latest["kinetics_summary"]
    assert {"enzymes", "buffers", "ligation_profiles", "metadata_tags"} <= kinetics_summary.keys()
    guardrails = latest["guardrail_heuristics"]
    assert guardrails["primers"]["primer_state"] in {"ok", "review"}
    assert latest["assembly_presets"]

    list_resp = client.get("/api/dna-assets", headers=headers)
    assert list_resp.status_code == 200
    assets = list_resp.json()
    assert any(a["id"] == asset["id"] for a in assets)


def test_versioning_and_diff(client, auth_headers):
    headers, user = auth_headers
    create_payload = {
        "name": "Diff Construct",
        "sequence": "ATGC" * 10,
    }
    create_resp = client.post("/api/dna-assets", json=create_payload, headers=headers)
    assert create_resp.status_code == 201
    asset = create_resp.json()

    update_payload = {
        "sequence": "ATGC" * 9 + "GGGG",
        "metadata": {"notes": "adjusted tail"},
    }
    version_resp = client.post(
        f"/api/dna-assets/{asset['id']}/versions",
        json=update_payload,
        headers=headers,
    )
    assert version_resp.status_code == 200
    updated = version_resp.json()
    assert updated["latest_version"]["version_index"] == 2

    diff_resp = client.get(
        f"/api/dna-assets/{asset['id']}/diff",
        params={
            "from_version": asset["latest_version"]["id"],
            "to_version": updated["latest_version"]["id"],
        },
        headers=headers,
    )
    assert diff_resp.status_code == 200
    diff = diff_resp.json()
    assert diff["substitutions"] >= 0
    assert diff["insertions"] >= 0


def test_dna_asset_residency_violation_creates_compliance_record(client, auth_headers):
    headers, user = auth_headers
    session = TestingSessionLocal()
    try:
        org_slug = f"helios-{uuid.uuid4().hex[:8]}"
        organization = models.Organization(
            name=f"Helios Labs {org_slug.split('-')[-1]}",
            slug=org_slug,
            primary_region="us-east-1",
            allowed_regions=["us-east-1"],
            encryption_policy={"at_rest": "kms"},
            retention_policy={},
        )
        session.add(organization)
        session.flush()
        policy = models.OrganizationResidencyPolicy(
            organization_id=organization.id,
            data_domain="dna_asset",
            allowed_regions=["us-east-1"],
            default_region="us-east-1",
            encryption_at_rest="kms",
            encryption_in_transit="tls1.3",
            retention_days=365,
            audit_interval_days=30,
            guardrail_flags=["encryption:strict"],
        )
        session.add(policy)
        session.commit()
        organization_id = organization.id
    finally:
        session.close()

    payload = {
        "name": "Residency Asset",
        "sequence": "ATGC" * 15,
        "metadata": {
            "compliance": {
                "organization_id": str(organization_id),
                "region": "eu-west-1",
                "data_domain": "dna_asset",
            }
        },
    }
    resp = client.post("/api/dna-assets", json=payload, headers=headers)
    assert resp.status_code == 201
    asset = resp.json()
    compliance_meta = asset["meta"].get("compliance")
    assert compliance_meta["allowed"] is False
    assert "residency:region_blocked" in compliance_meta["flags"]
    assert compliance_meta["effective_region"] == "us-east-1"

    session = TestingSessionLocal()
    try:
        records = (
            session.query(models.ComplianceRecord)
            .filter(
                models.ComplianceRecord.organization_id == organization_id,
                models.ComplianceRecord.record_type == "dna_asset",
            )
            .all()
        )
        assert records
        assert any(record.status == "restricted" for record in records)
    finally:
        session.close()


def test_guardrail_event_recording(client, auth_headers):
    headers, user = auth_headers
    payload = {
        "name": "Guardrail Asset",
        "sequence": "ATGC" * 12,
    }
    resp = client.post("/api/dna-assets", json=payload, headers=headers)
    assert resp.status_code == 201
    asset = resp.json()
    version_id = asset["latest_version"]["id"]

    event_payload = {
        "event_type": "qc.review",
        "details": {"status": "needs_review", "version_id": version_id},
    }
    event_resp = client.post(
        f"/api/dna-assets/{asset['id']}/guardrails",
        json=event_payload,
        headers=headers,
    )
    assert event_resp.status_code == 201
    event = event_resp.json()
    assert event["event_type"] == "qc.review"
    assert event["version_id"] == version_id

