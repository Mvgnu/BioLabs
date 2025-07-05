import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register", json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_create_and_get_template(client):
    headers = get_headers(client)
    create = client.post(
        "/api/protocols/templates",
        json={"name": "Prep", "content": "Step 1"},
        headers=headers,
    )
    assert create.status_code == 200
    data = create.json()
    tpl_id = data["id"]
    assert data["version"] == "1"

    get_resp = client.get(f"/api/protocols/templates/{tpl_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == tpl_id

    # create second version
    create2 = client.post(
        "/api/protocols/templates",
        json={"name": "Prep", "content": "Step 2"},
        headers=headers,
    )
    assert create2.json()["version"] == "2"

    list_resp = client.get("/api/protocols/templates", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 2

    # update template
    upd = client.put(
        f"/api/protocols/templates/{tpl_id}",
        json={"name": "Prep Updated", "content": "Updated"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["name"] == "Prep Updated"

    # delete template
    del_resp = client.delete(f"/api/protocols/templates/{tpl_id}", headers=headers)
    assert del_resp.status_code == 200
    list_after = client.get("/api/protocols/templates", headers=headers)
    assert all(t["id"] != tpl_id for t in list_after.json())


def test_protocol_execution_flow(client):
    headers = get_headers(client)
    tpl_resp = client.post(
        "/api/protocols/templates",
        json={"name": "Exec", "content": "Step"},
        headers=headers,
    )
    tpl_id = tpl_resp.json()["id"]

    exec_resp = client.post(
        "/api/protocols/executions",
        json={"template_id": tpl_id},
        headers=headers,
    )
    assert exec_resp.status_code == 200
    exec_id = exec_resp.json()["id"]
    assert exec_resp.json()["status"] == "pending"

    list_resp = client.get("/api/protocols/executions", headers=headers)
    assert any(e["id"] == exec_id for e in list_resp.json())

    upd_resp = client.put(
        f"/api/protocols/executions/{exec_id}",
        json={"status": "completed", "result": {"ok": True}},
        headers=headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["status"] == "completed"
    assert upd_resp.json()["result"] == {"ok": True}


def test_protocol_variables(client):
    headers = get_headers(client)
    tpl = client.post(
        "/api/protocols/templates",
        json={"name": "Var", "content": "Step", "variables": ["temp"]},
        headers=headers,
    ).json()

    # missing param should fail
    resp = client.post(
        "/api/protocols/executions",
        json={"template_id": tpl["id"], "params": {}},
        headers=headers,
    )
    assert resp.status_code == 400

    # providing param succeeds
    ok = client.post(
        "/api/protocols/executions",
        json={"template_id": tpl["id"], "params": {"temp": "20C"}},
        headers=headers,
    )
    assert ok.status_code == 200


def test_public_and_forking(client):
    headers = get_headers(client)
    tpl = client.post(
        "/api/protocols/templates",
        json={"name": "Pub", "content": "Step", "is_public": True},
        headers=headers,
    ).json()

    pub_list = client.get("/api/protocols/public")
    assert any(t["id"] == tpl["id"] for t in pub_list.json())

    fork = client.post(f"/api/protocols/templates/{tpl['id']}/fork", headers=headers)
    assert fork.status_code == 200
    assert fork.json()["forked_from"] == tpl["id"]


def test_protocol_merge_requests(client):
    headers = get_headers(client)
    tpl = client.post(
        "/api/protocols/templates",
        json={"name": "Pub2", "content": "A", "is_public": True},
        headers=headers,
    ).json()
    mr = client.post(
        "/api/protocols/merge-requests",
        json={"template_id": tpl["id"], "content": "B", "variables": ["x"]},
        headers=headers,
    )
    assert mr.status_code == 200
    mr_id = mr.json()["id"]

    # author lists and accepts
    mrs = client.get("/api/protocols/merge-requests", headers=headers)
    assert any(r["id"] == mr_id for r in mrs.json())

    accepted = client.post(f"/api/protocols/merge-requests/{mr_id}/accept", headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["content"] == "B"


def test_protocol_diff(client):
    headers = get_headers(client)
    tpl1 = client.post(
        "/api/protocols/templates",
        json={"name": "Diff", "content": "A"},
        headers=headers,
    ).json()
    tpl2 = client.post(
        "/api/protocols/templates",
        json={"name": "Diff", "content": "B"},
        headers=headers,
    ).json()
    resp = client.get(
        "/api/protocols/diff",
        params={"old_id": tpl1["id"], "new_id": tpl2["id"]},
        headers=headers,
    )
    assert resp.status_code == 200
    diff = resp.json()["diff"]
    assert "-A" in diff and "+B" in diff


def test_protocol_stars(client):
    headers = get_headers(client)
    tpl = client.post(
        "/api/protocols/templates",
        json={"name": "Star", "content": "s"},
        headers=headers,
    ).json()

    star = client.post(f"/api/protocols/templates/{tpl['id']}/star", headers=headers)
    assert star.status_code == 200
    data = client.get(f"/api/protocols/templates/{tpl['id']}/stars", headers=headers).json()
    assert data["count"] == 1

    # starring again has no effect
    client.post(f"/api/protocols/templates/{tpl['id']}/star", headers=headers)
    data = client.get(f"/api/protocols/templates/{tpl['id']}/stars", headers=headers).json()
    assert data["count"] == 1

    # unstar removes the star
    client.delete(f"/api/protocols/templates/{tpl['id']}/star", headers=headers)
    data = client.get(f"/api/protocols/templates/{tpl['id']}/stars", headers=headers).json()
    assert data["count"] == 0

