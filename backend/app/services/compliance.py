"""Compliance residency, encryption, and legal hold orchestration helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas

_UTC_NOW = datetime.now


def _utcnow() -> datetime:
    return _UTC_NOW(timezone.utc)


# purpose: persist and evaluate organization-level residency, encryption, and retention state
# status: experimental
# depends_on: backend.app.models.Organization, backend.app.models.OrganizationResidencyPolicy
# related_docs: docs/operations/data_residency.md


def list_organizations(db: Session) -> Sequence[models.Organization]:
    """Return all organizations ordered for administrative dashboards."""

    return (
        db.query(models.Organization)
        .options(
            joinedload(models.Organization.residency_policies),
            joinedload(models.Organization.legal_holds),
        )
        .order_by(models.Organization.name.asc())
        .all()
    )


def create_organization(db: Session, payload: schemas.OrganizationCreate) -> models.Organization:
    """Create a new organization with baseline residency defaults."""

    organization = models.Organization(
        name=payload.name,
        slug=payload.slug,
        primary_region=payload.primary_region,
        residency_enforced=payload.residency_enforced,
        allowed_regions=list(payload.allowed_regions or []),
        encryption_policy=dict(payload.encryption_policy or {}),
        retention_policy=dict(payload.retention_policy or {}),
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(organization)
    db.flush()
    db.refresh(organization)
    return organization


def update_organization(
    db: Session,
    *,
    organization: models.Organization,
    payload: schemas.OrganizationUpdate,
) -> models.Organization:
    """Mutate residency guardrails for an existing organization."""

    if payload.name is not None:
        organization.name = payload.name
    if payload.slug is not None:
        organization.slug = payload.slug
    if payload.primary_region is not None:
        organization.primary_region = payload.primary_region
    if payload.residency_enforced is not None:
        organization.residency_enforced = payload.residency_enforced
    if payload.allowed_regions is not None:
        organization.allowed_regions = list(payload.allowed_regions)
    if payload.encryption_policy is not None:
        organization.encryption_policy = dict(payload.encryption_policy)
    if payload.retention_policy is not None:
        organization.retention_policy = dict(payload.retention_policy)
    organization.updated_at = _utcnow()
    db.flush()
    db.refresh(organization)
    return organization


def upsert_residency_policy(
    db: Session,
    *,
    organization: models.Organization,
    payload: schemas.ResidencyPolicyPayload,
) -> models.OrganizationResidencyPolicy:
    """Create or replace a residency policy for the provided data domain."""

    policy = (
        db.query(models.OrganizationResidencyPolicy)
        .filter(
            models.OrganizationResidencyPolicy.organization_id == organization.id,
            models.OrganizationResidencyPolicy.data_domain == payload.data_domain,
        )
        .one_or_none()
    )
    if policy is None:
        policy = models.OrganizationResidencyPolicy(
            organization_id=organization.id,
            data_domain=payload.data_domain,
        )
        db.add(policy)
    policy.allowed_regions = list(payload.allowed_regions or [])
    policy.default_region = payload.default_region
    policy.encryption_at_rest = payload.encryption_at_rest
    policy.encryption_in_transit = payload.encryption_in_transit
    policy.retention_days = payload.retention_days
    policy.audit_interval_days = payload.audit_interval_days
    policy.guardrail_flags = list(payload.guardrail_flags or [])
    policy.updated_at = _utcnow()
    db.flush()
    db.refresh(policy)
    return policy


def list_residency_policies(
    db: Session,
    *,
    organization: models.Organization,
) -> Sequence[models.OrganizationResidencyPolicy]:
    """Return residency policies for administrative review."""

    return (
        db.query(models.OrganizationResidencyPolicy)
        .filter(models.OrganizationResidencyPolicy.organization_id == organization.id)
        .order_by(models.OrganizationResidencyPolicy.data_domain.asc())
        .all()
    )


def record_legal_hold(
    db: Session,
    *,
    organization: models.Organization,
    payload: schemas.LegalHoldCreate,
    actor: models.User | None,
) -> models.OrganizationLegalHold:
    """Activate a legal hold for the provided organization."""

    hold = models.OrganizationLegalHold(
        organization_id=organization.id,
        scope_type=payload.scope_type,
        scope_reference=payload.scope_reference,
        reason=payload.reason,
        status="active",
        initiated_by_id=getattr(actor, "id", None),
        created_at=_utcnow(),
    )
    db.add(hold)
    db.flush()
    db.refresh(hold)
    return hold


def release_legal_hold(
    db: Session,
    *,
    hold: models.OrganizationLegalHold,
    release_notes: str | None,
    actor: models.User | None,
) -> models.OrganizationLegalHold:
    """Close an existing legal hold with audit metadata."""

    hold.status = "released"
    hold.released_at = _utcnow()
    hold.released_by_id = getattr(actor, "id", None)
    hold.release_notes = release_notes
    db.flush()
    db.refresh(hold)
    return hold


def evaluate_residency_guardrails(
    db: Session,
    *,
    organization: models.Organization,
    region: str | None,
    data_domain: str,
) -> schemas.ResidencyEvaluation:
    """Assess whether the provided region satisfies residency policies."""

    region = region or organization.primary_region
    policy = (
        db.query(models.OrganizationResidencyPolicy)
        .filter(
            models.OrganizationResidencyPolicy.organization_id == organization.id,
            models.OrganizationResidencyPolicy.data_domain == data_domain,
        )
        .one_or_none()
    )
    flags: list[str] = []
    allowed = True
    effective_region = region
    if policy:
        allowed_regions = set(policy.allowed_regions or [])
        if allowed_regions and region not in allowed_regions:
            allowed = False
            flags.append("residency:region_blocked")
        if policy.guardrail_flags:
            flags.extend(policy.guardrail_flags)
        effective_region = policy.default_region if not allowed else region
    elif organization.residency_enforced and organization.allowed_regions:
        allowed_regions = set(organization.allowed_regions)
        if region not in allowed_regions:
            allowed = False
            flags.append("residency:organization_default")
    return schemas.ResidencyEvaluation(
        allowed=allowed,
        effective_region=effective_region,
        flags=flags,
    )


def build_compliance_report(
    db: Session,
    *,
    organization_ids: Iterable[UUID] | None = None,
) -> schemas.ComplianceReport:
    """Generate a residency, encryption, and retention compliance report."""

    query = db.query(models.Organization)
    if organization_ids:
        query = query.filter(models.Organization.id.in_(list(organization_ids)))
    organizations = query.all()
    policy_counts: dict[UUID, int] = {}
    hold_counts: dict[UUID, int] = {}
    residency_gaps: dict[UUID, list[str]] = defaultdict(list)
    for organization in organizations:
        policy_counts[organization.id] = len(organization.residency_policies)
        hold_counts[organization.id] = sum(1 for hold in organization.legal_holds if hold.status == "active")
        if organization.residency_enforced and not organization.allowed_regions:
            residency_gaps[organization.id].append("no_allowed_regions")
        for policy in organization.residency_policies:
            if not policy.allowed_regions:
                residency_gaps[organization.id].append(f"{policy.data_domain}:unbounded")
    record_counts = (
        db.query(
            models.ComplianceRecord.organization_id,
            models.ComplianceRecord.status,
            sa.func.count(models.ComplianceRecord.id),
        )
        .group_by(models.ComplianceRecord.organization_id, models.ComplianceRecord.status)
        .all()
    )
    status_totals: dict[UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for organization_id, status, count in record_counts:
        if organization_id:
            status_totals[organization_id][status] += int(count)
    organizations_payload = []
    for organization in organizations:
        org_payload = schemas.ComplianceOrganizationReport(
            id=organization.id,
            name=organization.name,
            primary_region=organization.primary_region,
            residency_enforced=organization.residency_enforced,
            policy_count=policy_counts.get(organization.id, 0),
            active_holds=hold_counts.get(organization.id, 0),
            residency_gaps=residency_gaps.get(organization.id, []),
            record_status_totals=status_totals.get(organization.id, {}),
        )
        organizations_payload.append(org_payload)
    generated_at = _utcnow()
    return schemas.ComplianceReport(generated_at=generated_at, organizations=organizations_payload)


def annotate_compliance_record(
    record: models.ComplianceRecord,
    evaluation: schemas.ResidencyEvaluation,
    *,
    policy: models.OrganizationResidencyPolicy | None,
) -> None:
    """Embed residency evaluation metadata into the compliance record."""

    record.guardrail_flags = evaluation.flags
    record.region = evaluation.effective_region
    if policy:
        record.data_domain = policy.data_domain
        record.retention_period_days = policy.retention_days
        record.encryption_profile = {
            "at_rest": policy.encryption_at_rest,
            "in_transit": policy.encryption_in_transit,
        }
    record.updated_at = _utcnow()

