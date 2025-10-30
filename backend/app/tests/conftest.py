import os
os.environ["TESTING"] = "1"
os.environ.setdefault("SECRET_KEY", "test-secret")
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
from pathlib import Path
import shutil

import tempfile
import uuid

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.main import app
from app.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def upload_dir(tmp_path):
    d = tmp_path / "uploads"
    d.mkdir()
    os.environ["UPLOAD_DIR"] = str(d)
    yield
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def ensure_access_token(client, *, email: str | None = None, password: str = "secret"):
    """
    biolab: purpose: ensure deterministic access tokens for tests while tolerating reused accounts
    biolab: inputs: fastapi TestClient, optional email override, password string
    biolab: outputs: tuple(access_token str, normalized email str)
    biolab: status: active
    """

    normalized_email = email or f"user-{uuid.uuid4()}@example.com"
    payload = {"email": normalized_email, "password": password}
    resp = client.post("/api/auth/register", json=payload)
    if resp.status_code == 200:
        data = resp.json()
    else:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 400 and body.get("detail") == "Email already registered":
            login_resp = client.post("/api/auth/login", json=payload)
            assert login_resp.status_code == 200, f"Login failed for existing user {normalized_email}: {login_resp.text}"
            data = login_resp.json()
        else:
            raise AssertionError(f"Unexpected auth bootstrap failure for {normalized_email}: {resp.status_code} {resp.text}")
    token = data.get("access_token")
    if not token:
        raise AssertionError(f"Authentication response missing token for {normalized_email}: {data}")
    return token, normalized_email


def ensure_auth_headers(client, *, email: str | None = None, password: str = "secret"):
    """
    biolab: purpose: convenience wrapper returning authorization headers for API tests
    biolab: depends_on: ensure_access_token
    biolab: outputs: tuple(headers dict, normalized email str)
    biolab: status: active
    """

    token, normalized_email = ensure_access_token(client, email=email, password=password)
    return {"Authorization": f"Bearer {token}"}, normalized_email
