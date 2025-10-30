from .conftest import client, ensure_auth_headers


def get_headers(client, email):
    headers, _ = ensure_auth_headers(client, email=email)
    return headers


def create_item(client, headers, name):
    resp = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": name},
        headers=headers,
    )
    return resp.json()["id"]


def test_create_relationship(client):
    headers = get_headers(client, "rel@example.com")
    item1 = create_item(client, headers, "Item1")
    item2 = create_item(client, headers, "Item2")

    resp = client.post(
        "/api/inventory/relationships",
        json={"from_item": item1, "to_item": item2, "relationship_type": "parent"},
        headers=headers,
    )
    assert resp.status_code == 200
    rel_id = resp.json()["id"]

    list_resp = client.get(
        f"/api/inventory/items/{item1}/relationships",
        headers=headers,
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert any(r["id"] == rel_id for r in data)


def test_relationship_graph(client):
    headers = get_headers(client, "graph@example.com")
    item1 = create_item(client, headers, "ItemA")
    item2 = create_item(client, headers, "ItemB")
    item3 = create_item(client, headers, "ItemC")

    client.post(
        "/api/inventory/relationships",
        json={"from_item": item1, "to_item": item2, "relationship_type": "link"},
        headers=headers,
    )
    client.post(
        "/api/inventory/relationships",
        json={"from_item": item2, "to_item": item3, "relationship_type": "link"},
        headers=headers,
    )

    resp = client.get(
        f"/api/inventory/items/{item1}/graph",
        params={"depth": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    graph = resp.json()
    node_ids = {n["id"] for n in graph["nodes"]}
    assert {item1, item2, item3} <= node_ids
    assert len(graph["edges"]) >= 2


def test_relationship_permission(client):
    h1 = get_headers(client, "owner@example.com")
    h2 = get_headers(client, "other@example.com")
    item1 = create_item(client, h1, "OwnerItem")
    item2 = create_item(client, h2, "OtherItem")

    resp = client.post(
        "/api/inventory/relationships",
        json={"from_item": item1, "to_item": item2, "relationship_type": "test"},
        headers=h2,
    )
    assert resp.status_code == 403

    resp2 = client.get(f"/api/inventory/items/{item1}/graph", headers=h2)
    assert resp2.status_code == 403
