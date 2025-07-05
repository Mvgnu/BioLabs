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

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.main import app
from app.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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
