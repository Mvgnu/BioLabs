from __future__ import annotations

from uuid import UUID

from app import auth, models, notify
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
            "requires_planner_link": True,
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
        "planner_session_id": "00000000-0000-0000-0000-000000000001",
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
            "requires_planner_link": True,
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
        "planner_session_id": "00000000-0000-0000-0000-000000000000",
    }
    release_resp = client.post(
        f"/api/sharing/repositories/{repository['id']}/releases",
        json=release_payload,
        headers=_auth_headers(owner_token),
    )
    assert release_resp.status_code == 201
    release = release_resp.json()
    assert release["guardrail_state"] == "custody_blocked"
    assert release["status"] == "requires_mitigation"
