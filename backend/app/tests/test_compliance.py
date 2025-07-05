import uuid
from .conftest import client


def get_headers(client):
    resp = client.post('/api/auth/register', json={'email': f'{uuid.uuid4()}@ex.com', 'password': 'secret'})
    return {'Authorization': f"Bearer {resp.json()['access_token']}"}


def test_compliance_flow(client):
    headers = get_headers(client)
    rec = client.post('/api/compliance/records', json={'record_type': 'safety', 'status': 'pending'}, headers=headers)
    assert rec.status_code == 200
    rec_id = rec.json()['id']

    upd = client.put(f'/api/compliance/records/{rec_id}', json={'status': 'approved'}, headers=headers)
    assert upd.status_code == 200
    assert upd.json()['status'] == 'approved'

    lst = client.get('/api/compliance/records', headers=headers)
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    summary = client.get('/api/compliance/summary', headers=headers)
    assert summary.status_code == 200
    data = summary.json()
    assert any(s['status'] == 'approved' and s['count'] == 1 for s in data)
