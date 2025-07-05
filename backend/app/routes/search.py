from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas
from .. import search as search_utils

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/items", response_model=List[schemas.InventoryItemOut])
async def search_items_route(
    q: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if not q:
        raise HTTPException(status_code=400, detail="Query required")
    return search_utils.search_items(q, db)

