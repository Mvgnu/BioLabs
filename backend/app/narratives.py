"""Narrative export helpers for protocol execution timelines."""

from __future__ import annotations

# purpose: provide reusable serialization utilities for compliance exports
# status: pilot
# related_docs: PLAN.md

from collections.abc import Sequence
from datetime import datetime, timezone
import json
from typing import Any

from . import models


def _format_timestamp(value: datetime | None) -> str:
    """Return a standardized ISO 8601 timestamp string."""

    # purpose: normalize timestamps for consistent narrative output
    # inputs: optional datetime value from models
    # outputs: ISO string in UTC with trailing Z or empty string
    # status: pilot
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _derive_summary(payload: dict[str, Any]) -> str | None:
    """Pick a concise summary string from the payload when available."""

    # purpose: identify human readable highlight from diverse payload shapes
    # inputs: payload dictionary persisted on an ExecutionEvent
    # outputs: optional summary string prioritizing narrative-friendly fields
    # status: pilot
    priority_fields = ("message", "note", "summary", "description", "status")
    for key in priority_fields:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_payload(payload: dict[str, Any]) -> str:
    """Serialize payload data into deterministic JSON for evidence blocks."""

    # purpose: produce reproducible JSON snippets suitable for compliance evidence
    # inputs: payload dictionary from execution events
    # outputs: pretty printed JSON string sorted by keys
    # status: pilot
    try:
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    except TypeError:
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            try:
                json.dumps({key: value})
                sanitized[key] = value
            except TypeError:
                sanitized[key] = str(value)
        return json.dumps(sanitized, indent=2, sort_keys=True, ensure_ascii=False)


def render_execution_narrative(
    execution: models.ProtocolExecution,
    events: Sequence[models.ExecutionEvent],
    *,
    template: models.ProtocolTemplate | None = None,
) -> str:
    """Convert execution telemetry into a compliance-ready Markdown narrative."""

    # purpose: convert execution telemetry into compliance narrative markdown
    # inputs: protocol execution record, ordered execution events, optional template context
    # outputs: Markdown string summarizing the execution for exports
    # status: pilot
    # depends_on: models.ProtocolExecution, models.ExecutionEvent
    header_name = template.name if template and template.name else "Protocol Execution"
    lines: list[str] = [f"# Execution Narrative — {header_name}", ""]

    lines.append("## Execution Summary")
    lines.append("")
    lines.append(f"- execution_id: `{execution.id}`")
    if template:
        lines.append(f"- protocol_template_id: `{template.id}`")
    if template and getattr(template, "version", None):
        lines.append(f"- protocol_version: `{template.version}`")
    lines.append(f"- status: `{execution.status}`")
    lines.append(f"- created_at: `{_format_timestamp(getattr(execution, 'created_at', None))}`")
    lines.append(f"- updated_at: `{_format_timestamp(getattr(execution, 'updated_at', None))}`")
    lines.append(f"- total_events: {len(events)}")
    lines.append("")

    for event in events:
        timestamp = _format_timestamp(getattr(event, "created_at", None))
        actor_name = getattr(getattr(event, "actor", None), "full_name", None) or getattr(
            getattr(event, "actor", None), "email", None
        ) or "System"
        lines.append(f"## [{timestamp}] {event.event_type} (#{event.sequence})")
        lines.append("")
        lines.append(f"- actor: {actor_name}")
        lines.append(f"- event_id: `{event.id}`")
        lines.append(f"- event_type: `{event.event_type}`")
        summary = None
        payload: dict[str, Any] = {}
        if isinstance(event.payload, dict):
            payload = event.payload
            summary = _derive_summary(payload)
        if summary:
            lines.append(f"- summary: {summary}")
        if payload:
            lines.append("- payload:")
            lines.append("")
            lines.append("```json")
            lines.append(_normalize_payload(payload))
            lines.append("```")
        lines.append("")

    document = "\n".join(lines).strip()
    if not document.endswith("\n"):
        document += "\n"
    return document


def render_preview_narrative(
    execution: models.ProtocolExecution,
    stage_insights: Sequence[object],
    *,
    template_snapshot: dict[str, Any] | None = None,
) -> str:
    """Build a scientist-facing governance preview narrative."""

    # purpose: annotate governance ladder simulations with SLA projections and blockers
    # inputs: protocol execution record, ordered stage insights, optional snapshot payload
    # outputs: Markdown narrative summarizing preview findings
    # status: pilot
    header_name = "Governance Preview"
    if template_snapshot and isinstance(template_snapshot.get("name"), str):
        header_name = f"Governance Preview — {template_snapshot['name']}"

    lines: list[str] = [f"# {header_name}", ""]
    lines.append("## Execution Context")
    lines.append("")
    lines.append(f"- execution_id: `{execution.id}`")
    lines.append(f"- protocol_template_id: `{execution.template_id}`")
    if template_snapshot:
        version = template_snapshot.get("version")
        if version is not None:
            lines.append(f"- template_version: `{version}`")
        captured_at = template_snapshot.get("captured_at")
        if captured_at:
            lines.append(f"- snapshot_captured_at: `{captured_at}`")
    lines.append("")

    lines.append("## Stage Insights")
    lines.append("")
    for insight in stage_insights:
        index = getattr(insight, "index", None)
        name = getattr(insight, "name", None)
        required_role = getattr(insight, "required_role", "unknown")
        status = getattr(insight, "status", "ready")
        sla_hours = getattr(insight, "sla_hours", None)
        projected_due_at = getattr(insight, "projected_due_at", None)
        blockers = getattr(insight, "blockers", []) or []
        required_actions = getattr(insight, "required_actions", []) or []
        auto_triggers = getattr(insight, "auto_triggers", []) or []

        lines.append(f"### Stage {index if index is not None else '?'} — {name or required_role}")
        lines.append("")
        lines.append(f"- required_role: `{required_role}`")
        lines.append(f"- status: `{status}`")
        if sla_hours is not None:
            lines.append(f"- sla_hours: `{sla_hours}`")
        if projected_due_at:
            lines.append(
                f"- projected_due_at: `{projected_due_at.isoformat() if hasattr(projected_due_at, 'isoformat') else projected_due_at}`"
            )
        if blockers:
            lines.append("- blockers:")
            for blocker in blockers:
                lines.append(f"  - {blocker}")
        if required_actions:
            lines.append("- required_actions:")
            for action in required_actions:
                lines.append(f"  - {action}")
        if auto_triggers:
            lines.append("- auto_triggers:")
            for trigger in auto_triggers:
                lines.append(f"  - {trigger}")
        lines.append("")

    document = "\n".join(lines).strip()
    if not document.endswith("\n"):
        document += "\n"
    return document
