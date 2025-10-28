from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.routes import experiment_console as experiment_routes


def _make_actor(name: str = "A Operator") -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), full_name=name, email=f"{name.split()[0].lower()}@example.com")


def test_serialize_override_lock_snapshot_with_active_lock() -> None:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    record = SimpleNamespace(
        id=uuid4(),
        recommendation_id="cadence_overload:baseline",
        execution_id=uuid4(),
        execution_hash="hash-1",
        reversal_lock_token="lock-123",
        reversal_lock_tier="override_actor",
        reversal_lock_tier_key="override_actor",
        reversal_lock_tier_level=80,
        reversal_lock_scope="execution",
        reversal_lock_acquired_at=now - timedelta(minutes=2),
        reversal_lock_actor=_make_actor("Pat Operator"),
        cooldown_expires_at=now + timedelta(minutes=5),
        cooldown_window_minutes=30,
    )

    snapshot = experiment_routes._serialize_override_lock_snapshot(record, now=now)

    assert snapshot["override_id"] == str(record.id)
    assert snapshot["lock"] is not None
    assert snapshot["lock"]["token"] == "lock-123"
    assert snapshot["lock"]["actor"]["name"] == "Pat Operator"
    assert snapshot["cooldown"]["window_minutes"] == 30
    assert snapshot["cooldown"]["remaining_seconds"] == 300


def test_apply_lock_event_state_updates_cooldown_and_release() -> None:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    override_id = str(uuid4())
    state = {
        "override_id": override_id,
        "lock": None,
        "cooldown": {
            "expires_at": None,
            "window_minutes": None,
            "remaining_seconds": None,
        },
        "execution_hash": "hash-2",
    }

    acquired_event = {
        "lock_event": {
            "override_id": override_id,
            "event_type": "acquired",
            "lock_token": "lock-456",
            "tier": "team_lead",
            "tier_level": 90,
            "tier_key": "team_lead",
            "scope": "execution",
            "actor": {"id": str(uuid4()), "name": "Lead Operator", "email": "lead@example.com"},
            "created_at": now.isoformat(),
            "cooldown_expires_at": (now + timedelta(minutes=2)).isoformat(),
            "cooldown_window_minutes": 45,
        }
    }

    experiment_routes._apply_lock_event_state(state, acquired_event, now=now)

    assert state["lock"]["token"] == "lock-456"
    assert state["lock"]["escalation_prompt"] == "Team Lead · Level 90 lock engaged"
    assert state["cooldown"]["expires_at"] is not None
    assert state["cooldown"]["window_minutes"] == 45
    assert state["cooldown"]["remaining_seconds"] == 120

    released_event = {
        "lock_event": {
            "override_id": override_id,
            "event_type": "released",
            "lock_token": None,
        }
    }

    experiment_routes._apply_lock_event_state(state, released_event, now=now)

    assert state["lock"] is None
    assert state["cooldown"]["window_minutes"] == 45
