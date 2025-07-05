from .conftest import client
from pathlib import Path
import uuid


def get_headers(client):
    email = f"file{uuid.uuid4()}@example.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": "secret"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_upload_file(client):
    headers = get_headers(client)
    # create item
    item_resp = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "FileSample"},
        headers=headers,
    )
    item_id = item_resp.json()["id"]

    file_content = b"testcontent"
    resp = client.post(
        "/api/files/upload",
        data={"item_id": item_id},
        files={"upload": ("test.txt", file_content, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    list_resp = client.get(f"/api/files/items/{item_id}", headers=headers)
    assert list_resp.status_code == 200
    assert any(f["id"] == file_id for f in list_resp.json())

    # ensure file exists
    path = Path(resp.json()["storage_path"])
    assert path.exists()


def _ab1_bytes() -> bytes:
    import gzip
    path = Path(__file__).parent / "data" / "sample.ab1.gz"
    with gzip.open(path, "rb") as fh:
        return fh.read()


def test_file_chromatogram(client):
    headers = get_headers(client)
    # create item
    item_resp = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "ChromSample"},
        headers=headers,
    )
    item_id = item_resp.json()["id"]

    data = _ab1_bytes()
    upload_resp = client.post(
        "/api/files/upload",
        data={"item_id": item_id},
        files={"upload": ("test.ab1", data, "application/octet-stream")},
        headers=headers,
    )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    chrom_resp = client.get(f"/api/files/{file_id}/chromatogram", headers=headers)
    assert chrom_resp.status_code == 200
    result = chrom_resp.json()
    assert len(result["sequence"]) > 10
    assert all(len(result["traces"][b]) > 0 for b in ["A", "C", "G", "T"])


def test_file_sequence_preview(client):
    headers = get_headers(client)
    item_resp = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "SeqSample"},
        headers=headers,
    )
    item_id = item_resp.json()["id"]

    fasta = b">s1\nATGC\n"
    upload_resp = client.post(
        "/api/files/upload",
        data={"item_id": item_id},
        files={"upload": ("test.fasta", fasta, "text/plain")},
        headers=headers,
    )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    seq_resp = client.get(f"/api/files/{file_id}/sequence", headers=headers)
    assert seq_resp.status_code == 200
    data = seq_resp.json()
    assert data[0]["id"] == "s1"
    assert data[0]["length"] == 4
