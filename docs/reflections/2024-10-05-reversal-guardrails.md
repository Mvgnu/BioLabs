# Reflection: Override Reversal Guardrails

## Highlights
- Introduced explicit cooldown window telemetry and UI surfacing so operators understand how long reversals remain protected.
- Added application-level lock tokens to block concurrent reversal submissions, reducing the risk of conflicting rollback outcomes.
- Extended documentation across backend and frontend modules to keep lineage governance contracts discoverable.

## Challenges
- SQLite-based tests lack `FOR UPDATE` semantics, so we modelled concurrency via optimistic lock tokens with TTL instead of relying on database row locks.
- Ensuring the lock lifecycle released correctly even when reversals abort required careful try/finally scoping.

## Follow-ups
- Consider promoting lock metadata to the experiment console UI so reviewers can see which operator currently holds a reversal lock.
- Explore persisting a cooldown audit log table to support after-action reviews of reversal safety windows.
