from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from .. import models, schemas
from ..external import search_pubmed

router = APIRouter(prefix="/api/external", tags=["external"])


@router.post("/pubmed", response_model=list[schemas.PubMedArticle])
async def pubmed_search(
    payload: schemas.PubMedQuery,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        return search_pubmed(payload.query, payload.limit)
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to reach PubMed")

