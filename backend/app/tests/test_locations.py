import uuid

from .test_inventory import get_auth_headers


def test_create_and_list_locations(client):
    headers = get_auth_headers(client)
    # create team
    team_resp = client.post('/api/teams/', json={'name': 'LocTeam'}, headers=headers)
    team_id = team_resp.json()['id']
    loc_resp = client.post('/api/locations/', json={'name': 'Freezer 1', 'team_id': team_id}, headers=headers)
    assert loc_resp.status_code == 200
    loc_id = loc_resp.json()['id']

    list_resp = client.get('/api/locations', headers=headers)
    assert any(l['id'] == loc_id for l in list_resp.json())

    # assign to item
    item = client.post('/api/inventory/items', json={'item_type': 'sample', 'name': 'L1', 'location_id': loc_id}, headers=headers).json()
    assert item['location_id'] == loc_id
