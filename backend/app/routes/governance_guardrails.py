from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, simulation
from ..analytics.governance import invalidate_governance_analytics_cache
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/governance/guardrails", tags=["governance"])

# purpose: expose guardrail simulation evaluation endpoints for governance operators
# status: pilot


def _require_execution_access(
    execution: models.ProtocolExecution | None,
    user: models.User,
) -> models.ProtocolExecution:
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    if not user.is_admin and execution.run_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to evaluate guardrails",
        )
    return execution


def _snapshot_from_payload(
    payload: schemas.GovernanceGuardrailStageSnapshot,
) -> simulation.StageSimulationSnapshot:
    return simulation.StageSimulationSnapshot(
        status=payload.status,
        sla_hours=payload.sla_hours,
        projected_due_at=payload.projected_due_at,
        blockers=list(payload.blockers or []),
        required_actions=list(payload.required_actions or []),
        auto_triggers=list(payload.auto_triggers or []),
        assignee_id=payload.assignee_id,
        delegate_id=payload.delegate_id,
    )


def _serialise_guardrail_record(
    record: models.GovernanceGuardrailSimulation,
) -> schemas.GovernanceGuardrailSimulationRecord:
    summary_payload = record.summary or {}
    summary = schemas.GovernanceGuardrailSummary(
        state=summary_payload.get("state", record.state or "clear"),
        reasons=list(summary_payload.get("reasons", [])),
        regressed_stage_indexes=list(summary_payload.get("regressed_stage_indexes", [])),
        projected_delay_minutes=int(summary_payload.get("projected_delay_minutes", 0)),
    )
    actor = record.actor
    actor_schema = schemas.UserOut.model_validate(actor) if actor is not None else None
    metadata = (record.payload or {}).get("metadata", {})
    return schemas.GovernanceGuardrailSimulationRecord(
        id=record.id,
        execution_id=record.execution_id,
        actor=actor_schema,
        summary=summary,
        metadata=metadata,
        created_at=record.created_at,
        state=record.state,
        projected_delay_minutes=record.projected_delay_minutes,
    )


@router.post(
    "/simulations",
    response_model=schemas.GovernanceGuardrailSimulationRecord,
)
def create_guardrail_simulation(
    request: schemas.GovernanceGuardrailSimulationRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceGuardrailSimulationRecord:
    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == request.execution_id)
        .first()
    )
    execution = _require_execution_access(execution, user)

    comparisons: list[simulation.StageSimulationComparison] = []
    for entry in request.comparisons:
        baseline = _snapshot_from_payload(entry.baseline)
        simulated = _snapshot_from_payload(entry.simulated)
        comparisons.append(
            simulation.StageSimulationComparison(
                index=entry.index,
                name=entry.name,
                required_role=entry.required_role,
                mapped_step_indexes=list(entry.mapped_step_indexes or []),
                gate_keys=list(entry.gate_keys or []),
                baseline=baseline,
                simulated=simulated,
            )
        )

    summary = simulation.evaluate_reversal_guardrails(comparisons)
    payload = request.model_dump(mode="json")
    summary_payload = {
        "state": summary.state,
        "reasons": summary.reasons,
        "regressed_stage_indexes": summary.regressed_stage_indexes,
        "projected_delay_minutes": summary.projected_delay_minutes,
    }

    record = models.GovernanceGuardrailSimulation(
        execution_id=execution.id,
        actor_id=user.id,
        state=summary.state,
        projected_delay_minutes=summary.projected_delay_minutes,
        payload=payload,
        summary=summary_payload,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    if summary.state == "blocked":
        invalidate_governance_analytics_cache(execution_ids=[execution.id])

    return _serialise_guardrail_record(record)


@router.get(
    "/simulations/{simulation_id}",
    response_model=schemas.GovernanceGuardrailSimulationRecord,
)
def get_guardrail_simulation(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceGuardrailSimulationRecord:
    record = (
        db.query(models.GovernanceGuardrailSimulation)
        .options(joinedload(models.GovernanceGuardrailSimulation.actor))
        .filter(models.GovernanceGuardrailSimulation.id == simulation_id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == record.execution_id)
        .first()
    )
    _require_execution_access(execution, user)
    return _serialise_guardrail_record(record)


@router.get(
    "/simulations",
    response_model=list[schemas.GovernanceGuardrailSimulationRecord],
)
def list_guardrail_simulations(
    execution_id: UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.GovernanceGuardrailSimulationRecord]:
    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == execution_id)
        .first()
    )
    execution = _require_execution_access(execution, user)

    query = (
        db.query(models.GovernanceGuardrailSimulation)
        .options(joinedload(models.GovernanceGuardrailSimulation.actor))
        .filter(models.GovernanceGuardrailSimulation.execution_id == execution.id)
        .order_by(models.GovernanceGuardrailSimulation.created_at.desc())
        .limit(max(limit, 1))
    )
    return [_serialise_guardrail_record(record) for record in query.all()]
