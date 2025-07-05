from .conftest import client
import pyotp

def test_register_and_login(client):
    resp = client.post("/api/auth/register", json={"email": "test@example.com", "password": "secret"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token
    resp2 = client.post("/api/auth/login", json={"email": "test@example.com", "password": "secret"})
    assert resp2.status_code == 200


def test_two_factor_flow(client):
    # register and login
    resp = client.post("/api/auth/register", json={"email": "2fa@example.com", "password": "secret"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    enable = client.post("/api/auth/enable-2fa", headers=headers)
    assert enable.status_code == 200
    secret = enable.json()["secret"]
    code = pyotp.TOTP(secret).now()
    verify = client.post("/api/auth/verify-2fa", json={"code": code}, headers=headers)
    assert verify.status_code == 200
    # login now requires otp
    fail = client.post("/api/auth/login", json={"email": "2fa@example.com", "password": "secret"})
    assert fail.status_code == 401
    success = client.post("/api/auth/login", json={"email": "2fa@example.com", "password": "secret", "otp_code": pyotp.TOTP(secret).now()})
    assert success.status_code == 200


def test_password_reset_flow(client):
    from app import notify
    notify.EMAIL_OUTBOX.clear()
    resp = client.post("/api/auth/register", json={"email": "reset@example.com", "password": "old"})
    assert resp.status_code == 200
    request = client.post("/api/auth/request-password-reset", json={"email": "reset@example.com"})
    assert request.status_code == 200
    token = notify.EMAIL_OUTBOX[-1][2].split()[-1]
    reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": "new"})
    assert reset.status_code == 200
    login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "new"})
    assert login.status_code == 200
