from uuid import UUID

from app import auth, models, notify
from app.routes import sharing as sharing_routes
from app.tests.conftest import TestingSessionLocal


def _register(client, email: str) -> str:
    session = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="test")
        session.add(user)
        session.commit()
        session.refresh(user)
    finally:
        session.close()
    return auth.create_access_token({"sub": email})


def _resolve_user_id(email: str) -> UUID:
    session = TestingSessionLocal()
    try:
        user = session.query(models.User).filter_by(email=email).first()
        assert user is not None
        return user.id
    finally:
        session.close()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_repository_release_flow(client):
    notify.EMAIL_OUTBOX.clear()
    owner_token = _register(client, "owner@example.com")
    maintainer_token = _register(client, "maintainer@example.com")
    maintainer_id = _resolve_user_id("maintainer@example.com")

    repo_payload = {
        "name": "Genome Vault",
        "slug": "genome-vault",
        "description": "Guarded workspace",
        "team_id": None,
        "guardrail_policy": {
            "name": "Strict",
            "approval_threshold": 1,
            "requires_custody_clearance": True,
            "requires_planner_link": False,
            "mitigation_playbooks": ["playbooks/custody-clearance"],
        },
    }
    repo_resp = client.post(
        "/api/sharing/repositories",
        json=repo_payload,
        headers=_auth_headers(owner_token),
    )
    assert repo_resp.status_code == 201, repo_resp.text
    repository = repo_resp.json()

    add_collab = client.post(
        f"/api/sharing/repositories/{repository['id']}/collaborators",
        json={"user_id": str(maintainer_id), "role": "maintainer"},
        headers=_auth_headers(owner_token),
    )
    assert add_collab.status_code == 201, add_collab.text

    release_payload = {
        "version": "v1.0.0",
        "title": "Initial Release",
        "notes": "Cleared",
        "guardrail_snapshot": {"custody_status": "clear", "breaches": []},
        "mitigation_summary": None,
        "lifecycle_snapshot": {"source": "planner", "checkpoint": "final"},
        "mitigation_history": [{"step": "custody-clear"}],
        "replay_checkpoint": {"checkpoint": "final"},
    }
    release_resp = client.post(
        f"/api/sharing/repositories/{repository['id']}/releases",
        json=release_payload,
        headers=_auth_headers(maintainer_token),
    )
    assert release_resp.status_code == 201, release_resp.text
    release = release_resp.json()
    assert release["guardrail_state"] == "cleared"
    assert release["status"] == "awaiting_approval"
    assert release["lifecycle_snapshot"]["checkpoint"] == "final"
    assert release["mitigation_history"][0]["step"] == "custody-clear"
    assert release["replay_checkpoint"]["checkpoint"] == "final"

    approval_resp = client.post(
        f"/api/sharing/releases/{release['id']}/approvals",
        json={"status": "approved", "guardrail_flags": [], "notes": "Looks good"},
        headers=_auth_headers(maintainer_token),
    )
    assert approval_resp.status_code == 200, approval_resp.text
    approved_release = approval_resp.json()
    assert approved_release["status"] == "published"
    assert approved_release["guardrail_state"] == "cleared"
    assert notify.EMAIL_OUTBOX, "Expected publication notification"

    timeline = client.get(
        f"/api/sharing/repositories/{repository['id']}/timeline",
        headers=_auth_headers(owner_token),
    )
    assert timeline.status_code == 200
    events = timeline.json()
    assert any(event["event_type"] == "release.published" for event in events)


def test_release_guardrail_block(client):
    owner_token = _register(client, "blocker@example.com")

    repo_payload = {
        "name": "Constraint",
        "slug": "constraint",
        "description": None,
        "team_id": None,
        "guardrail_policy": {
            "name": "Strict",
            "approval_threshold": 2,
            "requires_custody_clearance": True,
            "requires_planner_link": False,
            "mitigation_playbooks": [],
        },
    }
    repo_resp = client.post(
        "/api/sharing/repositories",
        json=repo_payload,
        headers=_auth_headers(owner_token),
    )
    assert repo_resp.status_code == 201
    repository = repo_resp.json()

    release_payload = {
        "version": "v0.1",
        "title": "Blocked Release",
        "notes": "Needs cleanup",
        "guardrail_snapshot": {"custody_status": "halted", "breaches": ["capacity.exceeded"]},
        "mitigation_summary": "Resolve custody",
    }
    release_resp = client.post(
        f"/api/sharing/repositories/{repository['id']}/releases",
        json=release_payload,
        headers=_auth_headers(owner_token),
    )
    assert release_resp.status_code == 201, release_resp.text
    release = release_resp.json()
    assert release["guardrail_state"] == "custody_blocked"
    assert release["status"] == "requires_mitigation"


def test_federation_channels_and_review_stream(client):
    notify.EMAIL_OUTBOX.clear()
    owner_token = _register(client, "federated-owner@example.com")
    maintainer_token = _register(client, "federated-maintainer@example.com")
    maintainer_id = _resolve_user_id("federated-maintainer@example.com")

    repo_payload = {
        "name": "Federated Genome",
        "slug": "federated-genome",
        "description": "Cross-org guardrails",
        "team_id": None,
        "guardrail_policy": {
            "name": "Federated",
            "approval_threshold": 1,
            "requires_custody_clearance": True,
            "requires_planner_link": False,
            "mitigation_playbooks": ["playbooks/federation"],
        },
    }
    repo_resp = client.post(
        "/api/sharing/repositories",
        json=repo_payload,
        headers=_auth_headers(owner_token),
    )
    assert repo_resp.status_code == 201, repo_resp.text
    repository = repo_resp.json()

    add_collab = client.post(
        f"/api/sharing/repositories/{repository['id']}/collaborators",
        json={"user_id": str(maintainer_id), "role": "maintainer"},
        headers=_auth_headers(owner_token),
    )
    assert add_collab.status_code == 201, add_collab.text

    release_payload = {
        "version": "v2.0.0",
        "title": "Federated Release",
        "notes": "Ready for partners",
        "guardrail_snapshot": {"custody_status": "clear", "breaches": []},
        "mitigation_summary": "",
        "lifecycle_snapshot": {"source": "planner", "checkpoint": "handoff"},
        "mitigation_history": [{"step": "custody-clear"}],
        "replay_checkpoint": {"checkpoint": "handoff"},
    }
    release_resp = client.post(
        f"/api/sharing/repositories/{repository['id']}/releases",
        json=release_payload,
        headers=_auth_headers(maintainer_token),
    )
    assert release_resp.status_code == 201, release_resp.text
    release = release_resp.json()

    approval_resp = client.post(
        f"/api/sharing/releases/{release['id']}/approvals",
        json={"status": "approved", "guardrail_flags": [], "notes": "Proceed"},
        headers=_auth_headers(maintainer_token),
    )
    assert approval_resp.status_code == 200, approval_resp.text

    link_payload = {
        "external_repository_id": "urn:repo:partners/genome",
        "external_organization": "Genome Partners",
        "permissions": {"push": False, "pull": True},
        "guardrail_contract": {"nda": True},
    }
    link_resp = client.post(
        f"/api/sharing/repositories/{repository['id']}/federation/links",
        json=link_payload,
        headers=_auth_headers(owner_token),
    )
    assert link_resp.status_code == 201, link_resp.text
    link = link_resp.json()

    attestation_payload = {
        "release_id": release["id"],
        "attestor_organization": "Genome Partners",
        "attestor_contact": "review@partners.test",
        "guardrail_summary": {"custody": "aligned"},
        "provenance_notes": "Synchronized guardrails",
    }
    attestation_resp = client.post(
        f"/api/sharing/federation/links/{link['id']}/attestations",
        json=attestation_payload,
        headers=_auth_headers(owner_token),
    )
    assert attestation_resp.status_code == 201, attestation_resp.text

    channel_payload = {
        "name": "Partner Channel",
        "slug": "partner",
        "description": "Partner distribution",
        "audience_scope": "partners",
        "guardrail_profile": {"requires_attestation": True},
        "federation_link_id": link["id"],
    }
    channel_resp = client.post(
        f"/api/sharing/repositories/{repository['id']}/channels",
        json=channel_payload,
        headers=_auth_headers(owner_token),
    )
    assert channel_resp.status_code == 201, channel_resp.text
    channel = channel_resp.json()

    channel_version_payload = {
        "release_id": release["id"],
        "version_label": "partners-1",
        "guardrail_attestation": {"custody": "clear"},
        "provenance_snapshot": {"link": link["id"]},
        "mitigation_digest": "No outstanding risks",
    }
    channel_version_resp = client.post(
        f"/api/sharing/channels/{channel['id']}/versions",
        json=channel_version_payload,
        headers=_auth_headers(owner_token),
    )
    assert channel_version_resp.status_code == 201, channel_version_resp.text

    session = TestingSessionLocal()
    try:
        repo_obj = session.get(models.DNARepository, UUID(repository["id"]))
        assert repo_obj is not None
        snapshot = sharing_routes._serialize_repository_snapshot(repo_obj)
    finally:
        session.close()

    assert snapshot["releases"], "Snapshot should include releases"
    assert snapshot["release_channels"], "Snapshot should include release channels"
    assert snapshot["federation_links"], "Snapshot should include federation links"

    events = sharing_routes._load_review_events(UUID(repository["id"]), None, None)
    assert events, "Expected timeline events for repository"

    payloads = [item for item, _, _ in events]
    event_types = {payload.get("event_type") for payload in payloads}
    assert {
        "release.published",
        "federation.attestation_recorded",
        "channel.version_published",
    }.issubset(event_types)

    attestation_events = [
        payload
        for payload in payloads
        if payload.get("event_type") == "federation.attestation_recorded"
    ]
    assert any(
        event.get("federation_link", {}).get("trust_state") == "attested"
        for event in attestation_events
    )

    channel_events = [
        payload
        for payload in payloads
        if payload.get("event_type") == "channel.version_published"
    ]
    assert any(
        payload.get("release_channel", {}).get("versions")
        for payload in channel_events
    )
