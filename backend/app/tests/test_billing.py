import uuid

from datetime import datetime, timedelta, timezone

from .conftest import TestingSessionLocal
from app import models


def auth_headers(client, email: str) -> dict[str, str]:
    resp = client.post('/api/auth/register', json={'email': email, 'password': 'secret'})
    token = resp.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_billing_subscription_and_usage_flow(client):
    headers = auth_headers(client, 'billing-admin@example.com')

    session = TestingSessionLocal()
    try:
        user = session.query(models.User).filter_by(email='billing-admin@example.com').first()
        user.is_admin = True
        org_suffix = uuid.uuid4().hex[:8]
        organization = models.Organization(
            id=uuid.uuid4(),
            name=f'Helix Labs {org_suffix}',
            slug=f'helix-{org_suffix}',
            primary_region='us-east-1',
            allowed_regions=['us-east-1'],
            encryption_policy={'at_rest': 'kms'},
            retention_policy={'dna_assets': 365},
        )
        session.add(organization)
        session.commit()
        user_id = user.id
        organization_id = organization.id
    finally:
        session.close()

    plans = client.get('/api/billing/plans', headers=headers).json()
    assert plans
    plan_id = plans[0]['id']

    subscription = client.post(
        f'/api/billing/organizations/{organization_id}/subscriptions',
        json={'plan_id': plan_id, 'billing_email': 'finance@helix.test', 'sla_acceptance': {'version': '1.0'}},
        headers=headers,
    ).json()
    assert subscription['status'] == 'active'
    subscription_id = subscription['id']

    usage_payload = {
        'organization_id': str(organization.id),
        'subscription_id': subscription_id,
        'team_id': None,
        'user_id': str(user_id),
        'service': 'instrumentation',
        'operation': 'run_completed',
        'unit_quantity': 1.0,
        'credits_consumed': 5,
        'guardrail_flags': [],
        'metadata': {'run_id': 'run-1'},
        'occurred_at': datetime.now(timezone.utc).isoformat(),
    }
    usage_event = client.post('/api/billing/usage', json=usage_payload, headers=headers).json()
    assert usage_event['credits_consumed'] == 5

    usage_events = client.get(
        f'/api/billing/organizations/{organization_id}/usage', headers=headers
    ).json()
    assert len(usage_events) == 1

    period_start = datetime.now(timezone.utc) - timedelta(days=30)
    period_end = datetime.now(timezone.utc)
    invoice = client.post(
        f'/api/billing/subscriptions/{subscription_id}/invoices/draft',
        json={'period_start': period_start.isoformat(), 'period_end': period_end.isoformat()},
        headers=headers,
    ).json()
    assert invoice['subscription_id'] == subscription_id

    invoices = client.get(
        f'/api/billing/subscriptions/{subscription_id}/invoices', headers=headers
    ).json()
    assert len(invoices) == 1

    ledger_entry = client.post(
        '/api/billing/credits/adjust',
        json={
            'subscription_id': subscription_id,
            'delta_credits': 20,
            'reason': 'manual_top_up',
            'metadata': {'note': 'test adjustment'},
        },
        headers=headers,
    ).json()
    assert ledger_entry['delta_credits'] == 20

    ledger = client.get(
        f'/api/billing/subscriptions/{subscription_id}/ledger', headers=headers
    ).json()
    assert any(entry['delta_credits'] == 20 for entry in ledger)
