from .conftest import client, ensure_auth_headers


def auth(client, email):
    headers, _ = ensure_auth_headers(client, email=email)
    return headers


def test_service_marketplace_flow(client):
    provider_h = auth(client, "prov@example.com")
    listing = client.post(
        "/api/services/listings",
        json={"name": "Sequencing", "description": "Sanger sequencing"},
        headers=provider_h,
    )
    assert listing.status_code == 200
    l_id = listing.json()["id"]

    listings = client.get("/api/services/listings").json()
    assert any(l["id"] == l_id for l in listings)

    requester_h = auth(client, "req@example.com")
    req = client.post(
        f"/api/services/listings/{l_id}/requests",
        json={"message": "Please sequence my plasmid"},
        headers=requester_h,
    )
    assert req.status_code == 200
    r_id = req.json()["id"]

    acc = client.post(f"/api/services/requests/{r_id}/accept", headers=provider_h)
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"

    # provider uploads result
    deliver = client.post(
        f"/api/services/requests/{r_id}/deliver",
        headers=provider_h,
        files={"upload": ("result.txt", b"done")},
    )
    assert deliver.status_code == 200
    assert deliver.json()["status"] == "completed"
    assert deliver.json()["result_file_id"] is not None

    # requester confirms payment
    paid = client.post(
        f"/api/services/requests/{r_id}/confirm-payment",
        headers=requester_h,
    )
    assert paid.status_code == 200
    assert paid.json()["payment_status"] == "paid"
