from .conftest import client
import uuid


def auth(client, email):
    resp = client.post("/api/auth/register", json={"email": email, "password": "secret"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_marketplace_flow(client):
    seller_h = auth(client, "seller@example.com")
    item = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "Item1"},
        headers=seller_h,
    ).json()
    listing = client.post(
        "/api/marketplace/listings",
        json={"item_id": item["id"], "price": 5},
        headers=seller_h,
    )
    assert listing.status_code == 200
    l_id = listing.json()["id"]

    listings = client.get("/api/marketplace/listings").json()
    assert any(l["id"] == l_id for l in listings)

    buyer_h = auth(client, "buyer@example.com")
    req = client.post(
        f"/api/marketplace/listings/{l_id}/requests",
        json={"message": "Interested"},
        headers=buyer_h,
    )
    assert req.status_code == 200
    r_id = req.json()["id"]

    acc = client.post(f"/api/marketplace/requests/{r_id}/accept", headers=seller_h)
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"
