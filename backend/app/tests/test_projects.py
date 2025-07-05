import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register", json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_project_flow(client):
    headers = get_headers(client)
    proj = client.post("/api/projects", json={"name": "Test"}, headers=headers)
    assert proj.status_code == 200
    proj_id = proj.json()["id"]

    item = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "S1"},
        headers=headers,
    ).json()

    add = client.post(
        f"/api/projects/{proj_id}/items",
        params={"item_id": item["id"]},
        headers=headers,
    )
    assert add.status_code == 204

    task = client.post(
        f"/api/projects/{proj_id}/tasks",
        json={"name": "Task1"},
        headers=headers,
    )
    assert task.status_code == 200
    task_id = task.json()["id"]

    upd = client.put(
        f"/api/projects/{proj_id}/tasks/{task_id}",
        json={"status": "done"},
        headers=headers,
    )
    assert upd.json()["status"] == "done"

    tasks = client.get(f"/api/projects/{proj_id}/tasks", headers=headers)
    assert any(t["id"] == task_id for t in tasks.json())

    del_task = client.delete(
        f"/api/projects/{proj_id}/tasks/{task_id}", headers=headers
    )
    assert del_task.status_code == 204

    lst = client.get("/api/projects", headers=headers)
    assert any(p["id"] == proj_id for p in lst.json())

    del_resp = client.delete(f"/api/projects/{proj_id}", headers=headers)
    assert del_resp.status_code == 204


def test_non_member_cannot_modify(client):
    owner = get_headers(client)
    proj = client.post("/api/projects", json={"name": "Sec"}, headers=owner).json()
    other = get_headers(client)
    resp = client.post(
        f"/api/projects/{proj['id']}/tasks",
        json={"name": "N"},
        headers=other,
    )
    assert resp.status_code == 403
