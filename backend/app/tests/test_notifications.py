import json
import uuid
import os
from .conftest import client, TestingSessionLocal
from app import notify, models, tasks, auth


def create_user(client, email, phone=None):
    db = TestingSessionLocal()
    user = models.User(
        email=email,
        hashed_password="secret",
        phone_number=phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    token = auth.create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_booking_notification(client):
    notify.EMAIL_OUTBOX.clear()
    notify.SMS_OUTBOX.clear()
    owner_headers = create_user(client, f"{uuid.uuid4()}@ex.com", phone="123")
    res = client.post(
        "/api/schedule/resources",
        json={"name": "Centrifuge"},
        headers=owner_headers,
    )
    assert res.status_code == 200
    resource_id = res.json()["id"]

    booker_headers = create_user(client, f"{uuid.uuid4()}@ex.com")
    booking = client.post(
        "/api/schedule/bookings",
        json={
            "resource_id": resource_id,
            "start_time": "2025-07-02T12:00:00",
            "end_time": "2025-07-02T13:00:00",
        },
        headers=booker_headers,
    )
    assert booking.status_code == 200

    notif_list = client.get("/api/notifications/", headers=owner_headers)
    assert notif_list.status_code == 200
    data = notif_list.json()
    assert len(data) == 1
    notif_id = data[0]["id"]
    assert "booked" in data[0]["message"]

    mark = client.post(f"/api/notifications/{notif_id}/read", headers=owner_headers)
    assert mark.status_code == 200
    assert mark.json()["is_read"] is True
    assert len(notify.EMAIL_OUTBOX) == 1
    assert len(notify.SMS_OUTBOX) == 1

def test_notification_preferences(client):
    notify.EMAIL_OUTBOX.clear()
    notify.SMS_OUTBOX.clear()
    owner_headers = create_user(client, f"{uuid.uuid4()}@ex.com", phone="555")
    # disable booking email notifications
    pref = client.put(
        "/api/notifications/preferences/booking/email",
        json={"enabled": False},
        headers=owner_headers,
    )
    assert pref.status_code == 200
    assert pref.json()["enabled"] is False

    res = client.post(
        "/api/schedule/resources",
        json={"name": "Incubator"},
        headers=owner_headers,
    )
    resource_id = res.json()["id"]

    booker_headers = create_user(client, f"{uuid.uuid4()}@ex.com")
    booking = client.post(
        "/api/schedule/bookings",
        json={
            "resource_id": resource_id,
            "start_time": "2025-07-02T15:00:00",
            "end_time": "2025-07-02T16:00:00",
        },
        headers=booker_headers,
    )
    assert booking.status_code == 200

    notif_list = client.get("/api/notifications/", headers=owner_headers)
    assert notif_list.status_code == 200
    assert len(notif_list.json()) == 1
    # email disabled but sms should still send
    assert len(notify.EMAIL_OUTBOX) == 0
    assert len(notify.SMS_OUTBOX) == 1


def test_daily_digest(client):
    notify.EMAIL_OUTBOX.clear()
    create_user(client, f"{uuid.uuid4()}@ex.com")
    email = f"{uuid.uuid4()}@ex.com"
    create_user(client, email)
    # create notifications directly
    db = TestingSessionLocal()
    user = db.query(models.User).filter_by(email=email).first()
    db.add(models.Notification(user_id=user.id, message="First"))
    db.add(models.Notification(user_id=user.id, message="Second"))
    db.commit()
    notify.send_daily_digest(db)
    db.close()
    entries = [e for e in notify.EMAIL_OUTBOX if e[0] == email]
    assert len(entries) == 1
    _, subject, body = entries[0]
    assert "Daily Notification Digest" in subject
    assert "First" in body and "Second" in body


def test_inventory_alert_task(client, monkeypatch):
    os.environ["INVENTORY_WARNING_DAYS"] = "7"
    notify.EMAIL_OUTBOX.clear()
    email = f"{uuid.uuid4()}@ex.com"
    headers = create_user(client, email)
    item = client.post(
        "/api/inventory/items",
        json={"item_type": "reagent", "name": "Buffer", "custom_data": {"stock": 1}},
        headers=headers,
    ).json()
    for _ in range(5):
        client.post(
            "/api/notebook/entries",
            json={"title": "use", "content": "c", "item_id": item["id"]},
            headers=headers,
        )
    tasks.check_inventory_levels()
    from .conftest import TestingSessionLocal
    db = TestingSessionLocal()
    user = db.query(models.User).filter_by(email=email).first()
    notifs = db.query(models.Notification).filter_by(user_id=user.id).all()
    db.close()
    assert any("may run out" in n.message for n in notifs)
    assert any(e[0] == email for e in notify.EMAIL_OUTBOX)


def test_preference_unique(client):
    email = f"{uuid.uuid4()}@ex.com"
    headers = create_user(client, email)
    for _ in range(2):
        res = client.put(
            "/api/notifications/preferences/booking/email",
            json={"enabled": True},
            headers=headers,
        )
        assert res.status_code == 200
    from .conftest import TestingSessionLocal
    db = TestingSessionLocal()
    user = db.query(models.User).filter_by(email=email).first()
    prefs = (
        db.query(models.NotificationPreference)
        .filter_by(user_id=user.id, pref_type="booking", channel="email")
        .all()
    )
    db.close()
    # only one preference row should exist
    assert len(prefs) == 1


def test_notification_events_published(client):
    email = f"{uuid.uuid4()}@ex.com"
    headers = create_user(client, email)

    team_resp = client.post("/api/teams/", json={"name": "Notify Team"}, headers=headers)
    assert team_resp.status_code == 200
    team_id = team_resp.json()["id"]

    db = TestingSessionLocal()
    user = db.query(models.User).filter_by(email=email).first()
    db.close()

    with client.websocket_connect(f"/ws/{team_id}") as websocket:
        create_resp = client.post(
            "/api/notifications/create",
            json={
                "user_id": str(user.id),
                "message": "Realtime hello",
                "title": "Greeting",
                "meta": {"action_url": "https://example.com"},
            },
            headers=headers,
        )
        assert create_resp.status_code == 200
        created_event = json.loads(websocket.receive_text())
        assert created_event["type"] == "notification_created"
        assert created_event["data"]["message"] == "Realtime hello"
        notif_id = created_event["data"]["id"]

        mark_resp = client.post(f"/api/notifications/{notif_id}/read", headers=headers)
        assert mark_resp.status_code == 200
        read_event = json.loads(websocket.receive_text())
        assert read_event["type"] == "notification_read"
        assert read_event["data"]["id"] == notif_id
        assert read_event["data"]["is_read"] is True

        delete_resp = client.delete(f"/api/notifications/{notif_id}", headers=headers)
        assert delete_resp.status_code == 200
        deleted_event = json.loads(websocket.receive_text())
        assert deleted_event["type"] == "notification_deleted"
        assert deleted_event["data"]["id"] == notif_id
