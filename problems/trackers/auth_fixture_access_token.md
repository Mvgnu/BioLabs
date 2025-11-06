## Problem Statement
KeyError exceptions were raised across multiple backend integration tests (inventory, relationships, services, marketplace, resource shares, websocket, labs, users, files, analytics, audit) when helper utilities attempted to register deterministic test accounts that already existed in the shared SQLite test database. The `/api/auth/register` endpoint returned a 400 error (`"Email already registered"`), causing test helpers to access a missing `access_token` key.

## Metadata
Status: Resolved
Priority: High
Type: Test
Next_Target: backend/app/tests/conftest.py

## Current Hypothesis
Registration helpers must gracefully handle pre-existing accounts by falling back to the login endpoint, ensuring deterministic email fixtures remain reusable between tests.

## Log of Attempts (Chronological)
- 2024-11-02T00:00:00Z — Verified failing helpers retrieved `resp.json()['access_token']` without guarding against registration conflicts. Identified repeated static emails in multiple suites as the trigger for the KeyError regression.
- 2024-11-02T00:00:00Z — Introduced `ensure_access_token`/`ensure_auth_headers` helpers within `backend/app/tests/conftest.py` that retry via `/api/auth/login` when registrations collide, updated affected test modules to consume the shared helper ensuring unique namespace handling.

## Resolution Summary
Centralized authentication helpers now handle pre-existing accounts by authenticating instead of re-registering, preventing KeyError exceptions when deterministic email fixtures collide in the shared SQLite test database.
