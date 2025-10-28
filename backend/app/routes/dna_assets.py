"""DNA asset lifecycle API routes."""

# purpose: expose CRUD, diffing, and governance endpoints for DNA assets
# status: experimental
# depends_on: backend.app.services.dna_assets, backend.app.schemas.dna_assets
# related_docs: docs/dna_assets.md

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import dna_assets

router = APIRouter(prefix="/api/dna-assets", tags=["dna-assets"])


def _assert_access(user: models.User, asset: models.DNAAsset) -> None:
    if user.is_admin:
        return
    if asset.created_by_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.post("", response_model=schemas.DNAAssetSummary, status_code=status.HTTP_201_CREATED)
def create_dna_asset(
    payload: schemas.DNAAssetCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.DNAAssetSummary:
    """Create a DNA asset and persist its initial version."""

    asset = dna_assets.create_asset(db, payload=payload, created_by=user)
    db.commit()
    db.refresh(asset)
    return dna_assets.serialize_asset(asset)


@router.get("", response_model=list[schemas.DNAAssetSummary])
def list_dna_assets(
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.DNAAssetSummary]:
    """List DNA assets with optional team filtering."""

    if team_id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team access denied")
    assets = dna_assets.list_assets(db, team_id=team_id)
    if not user.is_admin:
        assets = [asset for asset in assets if asset.created_by_id == user.id]
    return [dna_assets.serialize_asset(asset) for asset in assets]


@router.get("/{asset_id}", response_model=schemas.DNAAssetSummary)
def get_dna_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.DNAAssetSummary:
    """Fetch a DNA asset."""

    asset = dna_assets.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNA asset not found")
    _assert_access(user, asset)
    db.refresh(asset)
    return dna_assets.serialize_asset(asset)


@router.post("/{asset_id}/versions", response_model=schemas.DNAAssetSummary)
def add_dna_asset_version(
    asset_id: UUID,
    payload: schemas.DNAAssetVersionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.DNAAssetSummary:
    """Append a version to an existing DNA asset."""

    asset = dna_assets.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNA asset not found")
    _assert_access(user, asset)
    dna_assets.add_version(db, asset=asset, payload=payload, created_by=user)
    db.commit()
    db.refresh(asset)
    return dna_assets.serialize_asset(asset)


@router.get("/{asset_id}/diff", response_model=schemas.DNAAssetDiffResponse)
def diff_dna_asset_versions(
    asset_id: UUID,
    from_version: UUID = Query(..., description="Source version identifier"),
    to_version: UUID = Query(..., description="Target version identifier"),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.DNAAssetDiffResponse:
    """Compute diff between two DNA asset versions."""

    asset = dna_assets.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNA asset not found")
    _assert_access(user, asset)
    version_a = db.get(models.DNAAssetVersion, from_version)
    version_b = db.get(models.DNAAssetVersion, to_version)
    if not version_a or version_a.asset_id != asset.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source version not found")
    if not version_b or version_b.asset_id != asset.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target version not found")
    return dna_assets.diff_versions(version_a, version_b)


@router.post("/{asset_id}/guardrails", response_model=schemas.DNAAssetGuardrailEventOut, status_code=status.HTTP_201_CREATED)
def record_dna_asset_guardrail_event(
    asset_id: UUID,
    payload: schemas.DNAAssetGovernanceUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.DNAAssetGuardrailEventOut:
    """Record a governance guardrail event for an asset."""

    asset = dna_assets.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNA asset not found")
    _assert_access(user, asset)
    version = None
    version_ref = payload.details.get("version_id")
    if version_ref:
        version_id = version_ref if isinstance(version_ref, UUID) else UUID(str(version_ref))
        version = db.get(models.DNAAssetVersion, version_id)
        if not version or version.asset_id != asset.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found for guardrail event")
    event = dna_assets.record_guardrail_event(db, asset=asset, version=version, event=payload, created_by=user)
    db.commit()
    db.refresh(event)
    return dna_assets.serialize_guardrail_event(event)

