"""Sequence toolkit API surface exposing preset catalogs."""

# purpose: provide HTTP access to sequence toolkit preset metadata for planners
# status: experimental
# depends_on: backend.app.services.sequence_toolkit, backend.app.schemas.sequence_toolkit

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from .. import schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import sequence_toolkit

router = APIRouter(prefix="/api/sequence-toolkit", tags=["sequence-toolkit"])


@router.get("/presets", response_model=schemas.SequenceToolkitPresetCatalog)
def list_sequence_toolkit_presets(
    db=Depends(get_db),  # noqa: U100 - retained for parity with auth dependencies
    user=Depends(get_current_user),
) -> schemas.SequenceToolkitPresetCatalog:
    """Return curated toolkit presets for UI surfaces."""

    # purpose: expose deterministic toolkit preset catalog to authenticated clients
    catalog = sequence_toolkit.get_sequence_toolkit_presets()
    ordered = sorted(catalog.values(), key=lambda entry: entry.name.lower())
    presets = [schemas.SequenceToolkitPreset.model_validate(preset.model_dump()) for preset in ordered]
    return schemas.SequenceToolkitPresetCatalog(
        presets=presets,
        count=len(presets),
        generated_at=datetime.now(timezone.utc),
    )
