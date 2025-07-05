from .conftest import client
import uuid


def auth_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"seq{uuid.uuid4()}@example.com", "password": "secret"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_analyze_fasta(client):
    headers = auth_headers(client)
    fasta = b">seq1\nATGCGC\n>seq2\nAATT\n"
    resp = client.post(
        "/api/sequence/analyze",
        data={"format": "fasta"},
        files={"upload": ("test.fasta", fasta, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["id"] == "seq1"
    assert data[0]["length"] == 6


def test_sequence_job(client):
    headers = auth_headers(client)
    fasta = b">seq1\nATGC\n"
    resp = client.post(
        "/api/sequence/jobs",
        data={"format": "fasta"},
        files={"upload": ("test.fasta", fasta, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200
    job_id = resp.json()["id"]
    list_resp = client.get("/api/sequence/jobs", headers=headers)
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert any(j["id"] == job_id for j in jobs)
    job_resp = client.get(f"/api/sequence/jobs/{job_id}", headers=headers)
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert job_data["status"] == "completed"
    assert len(job_data["result"]) == 1



def test_sequence_alignment(client):
    headers = auth_headers(client)
    payload = {"seq1": "ACTG", "seq2": "ACGG", "mode": "global"}
    resp = client.post("/api/sequence/align", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "aligned_seq1" in data and "aligned_seq2" in data
    assert data["score"] > 0


def test_blast_search(client):
    headers = auth_headers(client)
    payload = {"query": "ACTGACTG", "subject": "ACTTACTG"}
    resp = client.post("/api/sequence/blast", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] > 0
    assert data["identity"] > 0


def test_primer_design(client):
    headers = auth_headers(client)
    payload = {"sequence": "ATGC" * 30, "size": 10}
    resp = client.post("/api/sequence/primers", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["forward"]["sequence"]) == 10
    assert len(data["reverse"]["sequence"]) == 10


def test_restriction_map(client):
    headers = auth_headers(client)
    payload = {"sequence": "GAATTCGAATTC", "enzymes": ["EcoRI"]}
    resp = client.post("/api/sequence/restriction", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["map"]
    assert "EcoRI" in data
    assert data["EcoRI"] == [2, 8]


def test_annotation(client):
    headers = auth_headers(client)
    gb = b"""LOCUS       test        40 bp DNA     linear   01-JAN-1980\nFEATURES             Location/Qualifiers\n     source          1..40\n     CDS             1..30\n                     /gene=\"x\"\nORIGIN\n        1 atggccattg taatgggccg ctgctgaaaa aa\n//\n"""
    resp = client.post(
        "/api/sequence/annotate",
        data={"format": "genbank"},
        files={"upload": ("test.gb", gb, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200
    feats = resp.json()
    assert any(f["type"] == "CDS" for f in feats)


from pathlib import Path


def _ab1_bytes() -> bytes:
    import gzip
    path = Path(__file__).parent / "data" / "sample.ab1.gz"
    with gzip.open(path, "rb") as fh:
        return fh.read()


def test_chromatogram(client):
    headers = auth_headers(client)
    data = _ab1_bytes()
    resp = client.post(
        "/api/sequence/chromatogram",
        files={"upload": ("test.ab1", data, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["sequence"]) > 10
    assert all(len(result["traces"][b]) > 0 for b in ["A", "C", "G", "T"])
