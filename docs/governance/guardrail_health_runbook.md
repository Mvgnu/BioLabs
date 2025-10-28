# Guardrail Health Dashboard Runbook

- purpose: Provide operational playbooks for the `/api/governance/guardrails/health` telemetry and dashboard widgets.
- status: active
- updated: 2025-07-11
- related_docs: docs/governance/operator_sop.md, docs/governance/export_enforcement_audit.md

## Telemetry Source
- The health endpoint aggregates sanitised queue payloads emitted via `services.approval_ladders.record_packaging_queue_state`. Only the whitelisted fields in `PACKAGING_EVENT_PAYLOAD_SPEC` are surfaced; verify sanitisation via pytest before extending payloads.【F:backend/app/services/approval_ladders.py†L307-L433】【F:backend/app/analytics/governance.py†L523-L659】
- Operators can request scoped reports with `GET /api/governance/guardrails/health?execution_id=<uuid>` when investigating a single dossier. Use the `limit` query string to bound payload volume during major incidents.【F:backend/app/routes/governance_guardrails.py†L81-L105】

## Thresholds & Alerts
- **Blocked exports**: Any non-zero `blocked` count triggers a P1 alert. Resolve by reviewing guardrail simulations and re-running API/CLI dry-runs (`?dry_run=true` / `--dry-run`) after corrective actions.
- **Awaiting approval backlog**: Alert when awaiting approvals exceed 5 for more than 30 minutes. Escalate through the SOP escalation procedure and document outcomes in the execution timeline.
- **Stale telemetry**: The dashboard should refresh within 30 seconds. If timestamps exceed 5 minutes, invalidate analytics caches and confirm Celery workers are online.

## Response Checklist
1. Capture the dashboard card screenshot or JSON payload for the incident log.
2. Run the CLI dry-run (`python -m backend.app.cli queue-narrative-export <export-id> --dry-run`) to confirm guardrails remain active without dispatching workers.
3. Update `docs/governance/operator_sop.md` if new remediation steps emerge, and append reflections to `docs/reflections/` after major incidents.
4. Close incidents only after guardrail health reports zero blocked exports and awaiting counts fall below threshold for two consecutive refreshes.

## Future Enhancements
- Integrate cloning planner guardrail signals once orchestration stages emit compatible payloads.
- Add Prometheus exporters that mirror the sanitised queue contract for cross-team observability.
