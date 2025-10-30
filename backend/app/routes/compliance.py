"""Compliance residency and enterprise governance API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
import sqlalchemy as sa
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import compliance as compliance_service

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


def _serialize_organization(org: models.Organization) -> schemas.OrganizationOut:
    return schemas.OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        primary_region=org.primary_region,
        residency_enforced=org.residency_enforced,
        allowed_regions=list(org.allowed_regions or []),
        encryption_policy=dict(org.encryption_policy or {}),
        retention_policy=dict(org.retention_policy or {}),
        created_at=org.created_at,
        updated_at=org.updated_at,
        policy_count=len(org.residency_policies or []),
        active_legal_holds=sum(1 for hold in org.legal_holds if hold.status == "active"),
    )


def _serialize_policy(policy: models.OrganizationResidencyPolicy) -> schemas.ResidencyPolicyOut:
    return schemas.ResidencyPolicyOut(
        id=policy.id,
        data_domain=policy.data_domain,
        allowed_regions=list(policy.allowed_regions or []),
        default_region=policy.default_region,
        encryption_at_rest=policy.encryption_at_rest,
        encryption_in_transit=policy.encryption_in_transit,
        retention_days=policy.retention_days,
        audit_interval_days=policy.audit_interval_days,
        guardrail_flags=list(policy.guardrail_flags or []),
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _serialize_hold(hold: models.OrganizationLegalHold) -> schemas.LegalHoldOut:
    return schemas.LegalHoldOut(
        id=hold.id,
        scope_type=hold.scope_type,
        scope_reference=hold.scope_reference,
        reason=hold.reason,
        status=hold.status,
        created_at=hold.created_at,
        released_at=hold.released_at,
        release_notes=hold.release_notes,
    )


def _get_organization_or_404(db: Session, organization_id: UUID) -> models.Organization:
    organization = db.get(models.Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


def _get_legal_hold_or_404(db: Session, hold_id: UUID) -> models.OrganizationLegalHold:
    hold = db.get(models.OrganizationLegalHold, hold_id)
    if not hold:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal hold not found")
    return hold


def _get_compliance_record_or_404(db: Session, record_id: UUID) -> models.ComplianceRecord:
    record = db.get(models.ComplianceRecord, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance record not found")
    return record


@router.get("/organizations", response_model=list[schemas.OrganizationOut])
async def list_organizations(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.OrganizationOut]:
    _ = user
    organizations = compliance_service.list_organizations(db)
    return [_serialize_organization(org) for org in organizations]


@router.post("/organizations", response_model=schemas.OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: schemas.OrganizationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.OrganizationOut:
    _ = user  # RBAC hook: reserved for future admin validation
    organization = compliance_service.create_organization(db, payload)
    db.commit()
    db.refresh(organization)
    return _serialize_organization(organization)


@router.put("/organizations/{organization_id}", response_model=schemas.OrganizationOut)
async def update_organization(
    organization_id: UUID,
    payload: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.OrganizationOut:
    _ = user
    organization = _get_organization_or_404(db, organization_id)
    organization = compliance_service.update_organization(db, organization=organization, payload=payload)
    db.commit()
    db.refresh(organization)
    return _serialize_organization(organization)


@router.get(
    "/organizations/{organization_id}/policies",
    response_model=list[schemas.ResidencyPolicyOut],
)
async def list_residency_policies(
    organization_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.ResidencyPolicyOut]:
    _ = user
    organization = _get_organization_or_404(db, organization_id)
    policies = compliance_service.list_residency_policies(db, organization=organization)
    return [_serialize_policy(policy) for policy in policies]


@router.post(
    "/organizations/{organization_id}/policies",
    response_model=schemas.ResidencyPolicyOut,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_residency_policy(
    organization_id: UUID,
    payload: schemas.ResidencyPolicyPayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ResidencyPolicyOut:
    _ = user
    organization = _get_organization_or_404(db, organization_id)
    policy = compliance_service.upsert_residency_policy(db, organization=organization, payload=payload)
    db.commit()
    db.refresh(policy)
    return _serialize_policy(policy)


@router.get(
    "/organizations/{organization_id}/legal-holds",
    response_model=list[schemas.LegalHoldOut],
)
async def list_legal_holds(
    organization_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.LegalHoldOut]:
    _ = user
    organization = _get_organization_or_404(db, organization_id)
    return [_serialize_hold(hold) for hold in organization.legal_holds]


@router.post(
    "/organizations/{organization_id}/legal-holds",
    response_model=schemas.LegalHoldOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_legal_hold(
    organization_id: UUID,
    payload: schemas.LegalHoldCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.LegalHoldOut:
    organization = _get_organization_or_404(db, organization_id)
    hold = compliance_service.record_legal_hold(db, organization=organization, payload=payload, actor=user)
    db.commit()
    db.refresh(hold)
    return _serialize_hold(hold)


@router.post("/legal-holds/{hold_id}/release", response_model=schemas.LegalHoldOut)
async def release_legal_hold(
    hold_id: UUID,
    payload: schemas.LegalHoldCreate | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.LegalHoldOut:
    hold = _get_legal_hold_or_404(db, hold_id)
    release_notes = payload.reason if payload else None
    hold = compliance_service.release_legal_hold(db, hold=hold, release_notes=release_notes, actor=user)
    db.commit()
    db.refresh(hold)
    return _serialize_hold(hold)


@router.get("/reports/export", response_model=schemas.ComplianceReport)
async def export_compliance_report(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ComplianceReport:
    _ = user
    report = compliance_service.build_compliance_report(db)
    return report


@router.get("/records", response_model=list[schemas.ComplianceRecordOut])
async def list_records(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.ComplianceRecordOut]:
    _ = user
    records = db.query(models.ComplianceRecord).order_by(models.ComplianceRecord.created_at.desc()).all()
    return [schemas.ComplianceRecordOut.model_validate(record) for record in records]


@router.post("/records", response_model=schemas.ComplianceRecordOut, status_code=status.HTTP_201_CREATED)
async def create_record(
    payload: schemas.ComplianceRecordPayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ComplianceRecordOut:
    organization = None
    policy = None
    evaluation = None
    if payload.organization_id:
        organization = _get_organization_or_404(db, payload.organization_id)
        evaluation = compliance_service.evaluate_residency_guardrails(
            db,
            organization=organization,
            region=payload.region,
            data_domain=payload.data_domain,
        )
        policy = (
            db.query(models.OrganizationResidencyPolicy)
            .filter(
                models.OrganizationResidencyPolicy.organization_id == organization.id,
                models.OrganizationResidencyPolicy.data_domain == payload.data_domain,
            )
            .one_or_none()
        )
    record = models.ComplianceRecord(
        item_id=payload.item_id,
        user_id=getattr(user, "id", None),
        organization_id=payload.organization_id,
        record_type=payload.record_type,
        data_domain=payload.data_domain,
        status=payload.status,
        notes=payload.notes,
        region=payload.region,
        encryption_profile={},
        guardrail_flags=[],
    )
    if evaluation:
        compliance_service.annotate_compliance_record(record, evaluation, policy=policy)
        if policy and policy.guardrail_flags:
            existing = set(record.guardrail_flags or [])
            for flag in policy.guardrail_flags:
                if flag not in existing:
                    record.guardrail_flags.append(flag)
    db.add(record)
    db.commit()
    db.refresh(record)
    return schemas.ComplianceRecordOut.model_validate(record)


@router.put("/records/{record_id}", response_model=schemas.ComplianceRecordOut)
async def update_record(
    record_id: UUID,
    payload: schemas.ComplianceRecordUpdatePayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ComplianceRecordOut:
    _ = user
    record = _get_compliance_record_or_404(db, record_id)
    if payload.status is not None:
        record.status = payload.status
    if payload.notes is not None:
        record.notes = payload.notes
    if payload.region is not None:
        record.region = payload.region
        if record.organization_id:
            organization = record.organization or _get_organization_or_404(db, record.organization_id)
            evaluation = compliance_service.evaluate_residency_guardrails(
                db,
                organization=organization,
                region=payload.region,
                data_domain=record.data_domain,
            )
            policy = (
                db.query(models.OrganizationResidencyPolicy)
                .filter(
                    models.OrganizationResidencyPolicy.organization_id == organization.id,
                    models.OrganizationResidencyPolicy.data_domain == record.data_domain,
                )
                .one_or_none()
            )
            compliance_service.annotate_compliance_record(record, evaluation, policy=policy)
            if policy and policy.guardrail_flags:
                existing = set(record.guardrail_flags or [])
                for flag in policy.guardrail_flags:
                    if flag not in existing:
                        record.guardrail_flags.append(flag)
    db.commit()
    db.refresh(record)
    return schemas.ComplianceRecordOut.model_validate(record)


@router.get("/summary", response_model=list[schemas.ComplianceSummaryRow])
async def compliance_summary(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.ComplianceSummaryRow]:
    _ = user
    rows = (
        db.query(
            models.ComplianceRecord.status,
            sa.func.count(models.ComplianceRecord.id),
        )
        .group_by(models.ComplianceRecord.status)
        .all()
    )
    return [schemas.ComplianceSummaryRow(status=row[0], count=int(row[1])) for row in rows]

