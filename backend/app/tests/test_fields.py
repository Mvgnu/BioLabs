import uuid
from .conftest import client


def get_headers(client):
    resp = client.post('/api/auth/register', json={'email': f'{uuid.uuid4()}@ex.com', 'password': 'secret'})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_create_update_delete_field(client):
    headers = get_headers(client)
    create = client.post('/api/fields/definitions', json={'entity_type': 'sample', 'field_key': 'color', 'field_label': 'Color', 'field_type': 'text'}, headers=headers)
    assert create.status_code == 200
    fid = create.json()['id']

    list_resp = client.get('/api/fields/definitions/sample', headers=headers)
    assert any(f['id'] == fid for f in list_resp.json())

    upd = client.put(f'/api/fields/definitions/{fid}', json={'entity_type': 'sample', 'field_key': 'color', 'field_label': 'Shade', 'field_type': 'text'}, headers=headers)
    assert upd.status_code == 200
    assert upd.json()['field_label'] == 'Shade'

    del_resp = client.delete(f'/api/fields/definitions/{fid}', headers=headers)
    assert del_resp.status_code == 204

    list_after = client.get('/api/fields/definitions/sample', headers=headers)
    assert all(f['id'] != fid for f in list_after.json())


def test_duplicate_field_not_allowed(client):
    headers = get_headers(client)
    data = {
        'entity_type': 'sample',
        'field_key': 'color',
        'field_label': 'Color',
        'field_type': 'text',
    }
    first = client.post('/api/fields/definitions', json=data, headers=headers)
    assert first.status_code == 200
    second = client.post('/api/fields/definitions', json=data, headers=headers)
    assert second.status_code == 400
