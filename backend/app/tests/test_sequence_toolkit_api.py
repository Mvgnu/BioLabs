from .test_inventory import get_auth_headers


def test_sequence_toolkit_presets_catalog(client):
    headers = get_auth_headers(client)
    response = client.get('/api/sequence-toolkit/presets', headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload['count'] >= 3
    assert len(payload['presets']) == payload['count']
    first = payload['presets'][0]
    assert 'preset_id' in first and first['preset_id']
    assert 'primer_overrides' in first
