from .conftest import client
import uuid

def get_headers(client):
    email = f"data{uuid.uuid4()}@example.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": "secret"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_csv_summary(client):
    headers = get_headers(client)
    csv = b"a,b\n1,2\n3,4\n"
    resp = client.post(
        "/api/data/summary",
        files={"upload": ("test.csv", csv, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["a"]["mean"] == 2.0
    assert data["b"]["mean"] == 3.0
