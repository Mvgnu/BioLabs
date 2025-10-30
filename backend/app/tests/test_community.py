import uuid


def auth_headers(client, email: str | None = None):
    address = email or f"{uuid.uuid4()}@example.com"
    resp = client.post('/api/auth/register', json={'email': address, 'password': 'secret'})
    token = resp.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def _create_dna_asset(client, headers):
    asset = client.post(
        '/api/dna-assets',
        json={'name': 'Community asset', 'sequence': 'ATGCGT'},
        headers=headers,
    ).json()
    client.post(
        f"/api/dna-assets/{asset['id']}/guardrails",
        json={'event_type': 'safety.review', 'details': {'guardrail_flags': ['biohazard.escalation']}},
        headers=headers,
    )
    return asset


def test_portfolio_creation_compiles_lineage(client):
    owner_headers = auth_headers(client)
    asset = _create_dna_asset(client, owner_headers)

    payload = {
        'slug': 'synthetic-insight-kit',
        'title': 'Synthetic insight kit',
        'summary': 'Replayable qPCR setup with mitigation guidance.',
        'license': 'CC-BY-4.0',
        'tags': ['qpcr', 'guardrail'],
        'assets': [
            {
                'asset_type': 'dna_asset',
                'asset_id': asset['id'],
                'meta': {'diff': '+A→T guardrail adjustment'},
            }
        ],
    }

    portfolio = client.post('/api/community/portfolios', json=payload, headers=owner_headers).json()
    assert portfolio['slug'] == payload['slug']
    assert portfolio['guardrail_flags'] == ['biohazard.escalation']
    assert portfolio['status'] == 'requires_review'
    assert portfolio['provenance']['dna_assets'][0]['id'] == asset['id']
    assert portfolio['mitigation_history'], 'expected mitigation history from guardrail events'
    assert portfolio['replay_checkpoints'] == []


def test_personal_feed_and_trending_surfaces_engagement(client):
    owner_headers = auth_headers(client)
    reviewer_headers = auth_headers(client)
    asset = _create_dna_asset(client, owner_headers)

    portfolio = client.post(
        '/api/community/portfolios',
        json={
            'slug': 'collab-protocols',
            'title': 'Collaborative protocols',
            'summary': 'Guardrail cleared protocols ready for federation.',
            'license': 'CC0',
            'tags': ['protocols'],
            'assets': [
                {'asset_type': 'dna_asset', 'asset_id': asset['id']},
            ],
        },
        headers=owner_headers,
    ).json()
    # clear guardrail flags through moderation to allow publication
    moderation = client.post(
        f"/api/community/portfolios/{portfolio['id']}/moderation",
        json={'outcome': 'cleared'},
        headers=owner_headers,
    ).json()
    assert moderation['outcome'] == 'cleared'

    engagement = client.post(
        f"/api/community/portfolios/{portfolio['id']}/engagements",
        json={'interaction': 'star'},
        headers=reviewer_headers,
    )
    assert engagement.status_code == 200

    feed = client.get('/api/community/feed', headers=reviewer_headers).json()
    assert any(entry['portfolio']['id'] == portfolio['id'] for entry in feed)

    trending = client.get('/api/community/trending', headers=reviewer_headers).json()
    assert trending['portfolios']
    assert any(entry['portfolio']['id'] == portfolio['id'] for entry in trending['portfolios'])


def test_moderation_transitions_guardrail_state(client):
    headers = auth_headers(client)
    asset = _create_dna_asset(client, headers)

    portfolio = client.post(
        '/api/community/portfolios',
        json={
            'slug': 'mitigation-dossier',
            'title': 'Mitigation dossier',
            'summary': 'Includes outstanding guardrail review items.',
            'license': 'restricted',
            'tags': ['compliance'],
            'assets': [{'asset_type': 'dna_asset', 'asset_id': asset['id']}],
        },
        headers=headers,
    ).json()
    assert portfolio['status'] == 'requires_review'

    cleared = client.post(
        f"/api/community/portfolios/{portfolio['id']}/moderation",
        json={'outcome': 'cleared', 'notes': 'Flags resolved by custody review.'},
        headers=headers,
    ).json()
    assert cleared['outcome'] == 'cleared'

    refreshed = client.get(f"/api/community/portfolios/{portfolio['id']}", headers=headers).json()
    assert refreshed['guardrail_flags'] == []
    assert refreshed['status'] == 'published'
