## Problem Statement
Running compliance-adjacent test modules sequentially caused sqlite IntegrityErrors because multiple suites seeded organizations with the same static slug ("helios"/"helix") against the shared test database.

## Metadata
Status: Resolved
Priority: High
Type: Test
Next_Target: backend/app/tests/test_dna_assets.py

## Current Hypothesis
Static organization slugs introduced during enterprise compliance fixture migrations collide when suites reuse the persistent sqlite schema, triggering UNIQUE constraint violations.

## Log of Attempts (Chronological)
- 2025-10-30T16:14:23+00:00 — Hypothesis: dna asset and cloning planner suites share the "helios" slug leading to collisions. Ran `pytest backend/app/tests/test_cloning_planner.py backend/app/tests/test_dna_assets.py -q` to reproduce and captured the UNIQUE constraint failure. Confirmed additional static slug usage in billing tests via `rg "slug=" backend/app/tests -n`.

## Resolution Summary
Namespaced organization slugs and names with uuid-derived suffixes across cloning planner, dna asset, and billing integration tests so each suite seeds a unique tenant when executed within the same sqlite session.
