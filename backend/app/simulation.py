"""Simulation helpers for experiment governance previews."""

from __future__ import annotations

# purpose: encapsulate governance preview calculations for reuse across routes
# status: pilot
# related_docs: docs/governance/preview.md

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Sequence
from uuid import UUID


@dataclass(slots=True)
class StageSimulationResult:
    # purpose: capture readiness and SLA projections for a ladder stage preview
    index: int
    name: str | None
    required_role: str
    status: str
    sla_hours: int | None
    projected_due_at: datetime | None
    blockers: list[str]
    required_actions: list[str]
    auto_triggers: list[str]
    assignee_id: UUID | None
    delegate_id: UUID | None


def _aggregate_step_signals(
    step_states: Iterable[object],
) -> tuple[list[str], list[str], list[str]]:
    """Combine blocking telemetry from orchestrated steps."""

    # purpose: deduplicate blockers and action recommendations for preview stages
    blockers: list[str] = []
    required_actions: list[str] = []
    auto_triggers: list[str] = []
    seen_blockers: set[str] = set()
    seen_actions: set[str] = set()
    seen_triggers: set[str] = set()
    for state in step_states:
        reason = getattr(state, "blocked_reason", None)
        if isinstance(reason, str) and reason.strip():
            normalized = reason.strip()
            if normalized not in seen_blockers:
                seen_blockers.add(normalized)
                blockers.append(normalized)
        actions = getattr(state, "required_actions", []) or []
        for action in actions:
            if isinstance(action, str) and action not in seen_actions:
                seen_actions.add(action)
                required_actions.append(action)
        triggers = getattr(state, "auto_triggers", []) or []
        for trigger in triggers:
            if isinstance(trigger, str) and trigger not in seen_triggers:
                seen_triggers.add(trigger)
                auto_triggers.append(trigger)
    return blockers, required_actions, auto_triggers


def build_stage_simulation(
    stage_blueprint: Sequence[dict[str, object]],
    *,
    default_stage_sla_hours: int | None,
    stage_overrides: dict[int, dict[str, object]],
    step_states: Sequence[object],
    generated_at: datetime,
) -> list[StageSimulationResult]:
    """Generate preview insights for each stage in a governance ladder."""

    # purpose: centralize ladder preview calculations with SLA projections
    # inputs: immutable stage blueprint, override mapping, step telemetry, timestamp
    # outputs: ordered preview simulation results for UI consumption
    # status: pilot
    blockers, required_actions, auto_triggers = _aggregate_step_signals(step_states)
    cumulative_hours = 0
    results: list[StageSimulationResult] = []
    for index, raw_stage in enumerate(stage_blueprint):
        stage_name = None
        required_role = "unknown"
        sla_hours: int | None = None
        if isinstance(raw_stage, dict):
            stage_name = raw_stage.get("name") if isinstance(raw_stage.get("name"), str) else None
            role_candidate = raw_stage.get("required_role")
            if isinstance(role_candidate, str):
                required_role = role_candidate
            sla_candidate = raw_stage.get("sla_hours")
            if isinstance(sla_candidate, int):
                sla_hours = sla_candidate
        override = stage_overrides.get(index, {})
        assignee_id = override.get("assignee_id")
        delegate_id = override.get("delegate_id")
        override_sla = override.get("sla_hours")
        if isinstance(override_sla, int):
            sla_hours = override_sla
        if sla_hours is None:
            sla_hours = default_stage_sla_hours
        projected_due_at = None
        if sla_hours is not None:
            cumulative_hours += sla_hours
            projected_due_at = generated_at + timedelta(hours=cumulative_hours)
        status = "blocked" if blockers else "ready"
        results.append(
            StageSimulationResult(
                index=index,
                name=stage_name,
                required_role=required_role,
                status=status,
                sla_hours=sla_hours,
                projected_due_at=projected_due_at,
                blockers=list(blockers),
                required_actions=list(required_actions),
                auto_triggers=list(auto_triggers),
                assignee_id=assignee_id if isinstance(assignee_id, UUID) else None,
                delegate_id=delegate_id if isinstance(delegate_id, UUID) else None,
            )
        )
    return results


def normalize_stage_overrides(
    overrides: Sequence[object],
) -> dict[int, dict[str, object]]:
    """Transform override models into a dictionary keyed by stage index."""

    # purpose: provide stable mapping for simulation calculations
    normalized: dict[int, dict[str, object]] = {}
    for override in overrides:
        index = getattr(override, "index", None)
        if not isinstance(index, int):
            continue
        normalized[index] = {
            "assignee_id": getattr(override, "assignee_id", None),
            "delegate_id": getattr(override, "delegate_id", None),
            "sla_hours": getattr(override, "sla_hours", None),
        }
    return normalized

