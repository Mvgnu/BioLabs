"""Simulation helpers for experiment governance previews."""

from __future__ import annotations

# purpose: encapsulate governance preview calculations for reuse across routes
# status: pilot
# related_docs: docs/governance/preview.md

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Sequence, Literal
from uuid import UUID


@dataclass(slots=True)
class StageSimulationSnapshot:
    """Computed readiness state for a single stage perspective."""

    # purpose: expose baseline or simulated ladder state for diffing
    # inputs: aggregated step telemetry, SLA projection, role assignments
    # outputs: snapshot describing readiness, blockers, and delegation
    # status: pilot
    status: str
    sla_hours: int | None
    projected_due_at: datetime | None
    blockers: list[str]
    required_actions: list[str]
    auto_triggers: list[str]
    assignee_id: UUID | None
    delegate_id: UUID | None


@dataclass(slots=True)
class StageSimulationComparison:
    """Pair of baseline and simulated stage states for diff views."""

    # purpose: return diff-ready ladder data to preview consumers
    # inputs: baseline blueprint defaults and override scenario results
    # outputs: structured comparison for downstream serialization
    # status: pilot
    index: int
    name: str | None
    required_role: str
    mapped_step_indexes: list[int]
    gate_keys: list[str]
    baseline: StageSimulationSnapshot
    simulated: StageSimulationSnapshot


@dataclass(slots=True)
class ReversalForecastGuardrail:
    """Aggregate guardrail outcome for reversal simulations."""

    # purpose: summarize guardrail evaluation for reversal preview scenarios
    # inputs: evaluated stage comparison set containing baseline vs simulated states
    # outputs: aggregate status, triggers, and aggregate delay metadata for guardrail enforcement
    # status: pilot
    state: Literal["clear", "blocked"]
    reasons: list[str]
    regressed_stage_indexes: list[int]
    projected_delay_minutes: int


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


def _coerce_uuid(value: object) -> UUID | None:
    """Attempt to coerce arbitrary metadata values into UUIDs."""

    # purpose: normalize metadata-provided identifiers for simulation snapshots
    # inputs: potential UUID-like objects (UUID, str, None)
    # outputs: UUID instance when parsing succeeds else None
    # status: pilot
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _resolve_stage_indexes(
    *,
    explicit_indexes: Iterable[object],
    gate_keys: Iterable[object],
    step_count: int,
    step_requirements: Mapping[object, object] | None,
) -> set[int]:
    """Determine which execution steps map into the provided stage."""

    # purpose: translate blueprint metadata into concrete step groupings
    # inputs: explicit index list, gate key hints, step count, requirements mapping
    # outputs: set of resolved step indexes associated with the stage
    # status: pilot
    resolved: set[int] = set()
    for value in explicit_indexes:
        if isinstance(value, int) and 0 <= value < step_count:
            resolved.add(value)
        elif isinstance(value, str):
            try:
                numeric = int(value)
            except ValueError:
                continue
            if 0 <= numeric < step_count:
                resolved.add(numeric)

    normalized_gate_keys = [
        key.strip()
        for key in gate_keys
        if isinstance(key, str) and key.strip()
    ]
    if not normalized_gate_keys or not step_requirements:
        return resolved

    requirement_items = (
        step_requirements.items()
        if isinstance(step_requirements, Mapping)
        else []
    )
    hint_fields = (
        "gate_key",
        "gate_keys",
        "stage_gate_key",
        "stage_gate_keys",
    )
    for raw_index, config in requirement_items:
        if not isinstance(config, dict):
            continue
        associated_keys: set[str] = set()
        for field in hint_fields:
            value = config.get(field)
            if isinstance(value, str) and value.strip():
                associated_keys.add(value.strip())
            elif isinstance(value, (list, tuple, set)):
                for entry in value:
                    if isinstance(entry, str) and entry.strip():
                        associated_keys.add(entry.strip())
        if not associated_keys.intersection(normalized_gate_keys):
            continue
        index_value: int | None = None
        if isinstance(raw_index, int):
            index_value = raw_index
        elif isinstance(raw_index, str):
            try:
                index_value = int(raw_index)
            except ValueError:
                index_value = None
        if index_value is None or not (0 <= index_value < step_count):
            continue
        resolved.add(index_value)
    return resolved


def _distribute_unassigned_steps(
    stage_step_sets: list[set[int]],
    step_count: int,
) -> list[list[int]]:
    """Ensure every step is attributed to at least one stage."""

    # purpose: fallback assignment so analytics remain informative without metadata
    # inputs: stage step index sets and total step count
    # outputs: deterministic stage index lists covering all steps
    # status: pilot
    if not stage_step_sets:
        return []
    assigned: set[int] = set()
    for bucket in stage_step_sets:
        assigned.update(bucket)
    unassigned = [index for index in range(step_count) if index not in assigned]
    if unassigned:
        stage_count = len(stage_step_sets)
        pointer = 0
        for step_index in unassigned:
            target = stage_step_sets[pointer % stage_count]
            target.add(step_index)
            pointer += 1
    return [sorted(bucket) for bucket in stage_step_sets]


def build_stage_simulation(
    stage_blueprint: Sequence[dict[str, object]],
    *,
    default_stage_sla_hours: int | None,
    stage_overrides: dict[int, dict[str, object]],
    step_states: Sequence[object],
    step_requirements: Mapping[object, object] | None = None,
    generated_at: datetime,

) -> list[StageSimulationComparison]:
    """Generate baseline and override simulations for ladder stages."""

    # purpose: centralize ladder preview calculations with SLA projections
    # inputs: immutable stage blueprint, override mapping, step telemetry, timestamp
    # outputs: ordered preview comparison results for UI consumption
    # status: pilot
    step_count = len(step_states)
    normalized_requirements: Mapping[object, object] | None = (
        step_requirements if isinstance(step_requirements, Mapping) else None
    )

    stage_descriptors: list[dict[str, object]] = []
    stage_step_sets: list[set[int]] = []
    for index, raw_stage in enumerate(stage_blueprint):
        name = None
        required_role = "unknown"
        sla_hours: int | None = None
        metadata: dict[str, object] = {}
        step_indexes: list[object] = []
        gate_keys: list[object] = []
        if isinstance(raw_stage, dict):
            name = raw_stage.get("name") if isinstance(raw_stage.get("name"), str) else None
            role_candidate = raw_stage.get("required_role")
            if isinstance(role_candidate, str) and role_candidate.strip():
                required_role = role_candidate
            sla_candidate = raw_stage.get("sla_hours")
            if isinstance(sla_candidate, int):
                sla_hours = sla_candidate
            metadata_candidate = raw_stage.get("metadata")
            if isinstance(metadata_candidate, dict):
                metadata = metadata_candidate
            raw_step_indexes = raw_stage.get("stage_step_indexes")
            if isinstance(raw_step_indexes, (list, tuple, set)):
                step_indexes = list(raw_step_indexes)
            raw_gate_keys = raw_stage.get("stage_gate_keys")
            if isinstance(raw_gate_keys, (list, tuple, set)):
                gate_keys = list(raw_gate_keys)
        descriptor = {
            "index": index,
            "name": name,
            "required_role": required_role,
            "sla_hours": sla_hours,
            "metadata": metadata,
            "step_indexes": step_indexes,
            "gate_keys": gate_keys,
        }
        stage_descriptors.append(descriptor)
        stage_step_sets.append(
            _resolve_stage_indexes(
                explicit_indexes=step_indexes,
                gate_keys=gate_keys,
                step_count=step_count,
                step_requirements=normalized_requirements,
            )
        )

    resolved_stage_indexes = _distribute_unassigned_steps(stage_step_sets, step_count)

    cumulative_baseline_hours = 0
    cumulative_override_hours = 0
    comparisons: list[StageSimulationComparison] = []
    for descriptor, mapped_indexes in zip(stage_descriptors, resolved_stage_indexes):
        stage_index = descriptor["index"]
        stage_name = descriptor["name"]
        required_role = descriptor["required_role"]
        blueprint_sla: int | None = descriptor["sla_hours"]
        metadata = descriptor["metadata"]
        gate_keys = [
            key
            for key in descriptor["gate_keys"]
            if isinstance(key, str) and key
        ]

        baseline_sla = blueprint_sla if blueprint_sla is not None else default_stage_sla_hours
        override_config = stage_overrides.get(stage_index, {})
        override_assignee = override_config.get("assignee_id")
        override_delegate = override_config.get("delegate_id")
        override_sla_candidate = override_config.get("sla_hours")
        simulated_sla = (
            override_sla_candidate
            if isinstance(override_sla_candidate, int)
            else baseline_sla
        )

        baseline_assignee = None
        baseline_delegate = None
        if isinstance(metadata, dict):
            baseline_assignee = _coerce_uuid(metadata.get("assignee_id"))
            baseline_delegate = _coerce_uuid(metadata.get("delegate_id"))

        mapped_states = [
            step_states[index]
            for index in mapped_indexes
            if 0 <= index < len(step_states)
        ]
        blockers, required_actions, auto_triggers = _aggregate_step_signals(
            mapped_states
        )
        status = "blocked" if blockers else "ready"

        baseline_projected_due_at = None
        if baseline_sla is not None:
            cumulative_baseline_hours += baseline_sla
            baseline_projected_due_at = generated_at + timedelta(
                hours=cumulative_baseline_hours
            )

        simulated_projected_due_at = None
        if simulated_sla is not None:
            cumulative_override_hours += simulated_sla
            simulated_projected_due_at = generated_at + timedelta(
                hours=cumulative_override_hours
            )

        baseline_snapshot = StageSimulationSnapshot(
            status=status,
            sla_hours=baseline_sla,
            projected_due_at=baseline_projected_due_at,
            blockers=list(blockers),
            required_actions=list(required_actions),
            auto_triggers=list(auto_triggers),
            assignee_id=baseline_assignee,
            delegate_id=baseline_delegate,
        )
        simulated_snapshot = StageSimulationSnapshot(
            status=status,
            sla_hours=simulated_sla,
            projected_due_at=simulated_projected_due_at,
            blockers=list(blockers),
            required_actions=list(required_actions),
            auto_triggers=list(auto_triggers),
            assignee_id=_coerce_uuid(override_assignee) or baseline_assignee,
            delegate_id=_coerce_uuid(override_delegate) or baseline_delegate,
        )

        comparisons.append(
            StageSimulationComparison(
                index=stage_index,
                name=stage_name,
                required_role=required_role,
                mapped_step_indexes=mapped_indexes,
                gate_keys=gate_keys,
                baseline=baseline_snapshot,
                simulated=simulated_snapshot,
            )
        )
    return comparisons


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


def evaluate_reversal_guardrails(
    comparisons: Sequence[StageSimulationComparison],
) -> ReversalForecastGuardrail:
    """Determine whether simulated reversal changes breach guardrails."""

    # purpose: detect guardrail regressions introduced by reversal simulations
    # inputs: ordered stage comparisons containing baseline and simulated snapshots
    # outputs: consolidated guardrail state with supporting reasons and delay totals
    # status: pilot
    reasons: list[str] = []
    regressed_stage_indexes: list[int] = []
    total_delay_minutes = 0
    seen_reasons: set[str] = set()

    for comparison in comparisons:
        baseline = comparison.baseline
        simulated = comparison.simulated
        stage_reasons: list[str] = []

        baseline_blockers = set(baseline.blockers)
        simulated_blockers = [
            blocker for blocker in simulated.blockers if blocker not in baseline_blockers
        ]

        if baseline.status == "ready" and simulated.status != "ready":
            stage_reasons.append(
                f"stage_{comparison.index}:status_regression:{simulated.status}"
            )
        elif simulated_blockers:
            joined = ", ".join(simulated_blockers)
            stage_reasons.append(
                f"stage_{comparison.index}:new_blockers:{joined}"
            )

        if (
            baseline.projected_due_at is not None
            and simulated.projected_due_at is not None
        ):
            delta_seconds = (
                simulated.projected_due_at - baseline.projected_due_at
            ).total_seconds()
            delay_minutes = int(delta_seconds // 60)
            if delay_minutes > 0:
                total_delay_minutes += delay_minutes
                stage_reasons.append(
                    f"stage_{comparison.index}:due_delay_minutes:{delay_minutes}"
                )

        if (
            baseline.sla_hours is not None
            and simulated.sla_hours is not None
            and simulated.sla_hours > baseline.sla_hours
        ):
            delta_hours = simulated.sla_hours - baseline.sla_hours
            stage_reasons.append(
                f"stage_{comparison.index}:sla_increase_hours:{delta_hours}"
            )

        if stage_reasons:
            regressed_stage_indexes.append(comparison.index)
            for reason in stage_reasons:
                if reason not in seen_reasons:
                    seen_reasons.add(reason)
                    reasons.append(reason)

    state: Literal["clear", "blocked"] = "blocked" if reasons else "clear"
    return ReversalForecastGuardrail(
        state=state,
        reasons=reasons,
        regressed_stage_indexes=regressed_stage_indexes,
        projected_delay_minutes=total_delay_minutes,
    )

