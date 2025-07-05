from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/fields", tags=["fields"])

@router.post("/definitions", response_model=schemas.FieldDefinitionOut)
async def create_field(field: schemas.FieldDefinitionCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = db.query(models.FieldDefinition).filter(
        models.FieldDefinition.entity_type == field.entity_type,
        models.FieldDefinition.field_key == field.field_key,
    )
    team_id = getattr(field, "team_id", None)
    if team_id is None:
        query = query.filter(models.FieldDefinition.team_id.is_(None))
    else:
        query = query.filter(models.FieldDefinition.team_id == team_id)
    existing = query.first()
    if existing:
        raise HTTPException(status_code=400, detail="Field already exists")
    db_field = models.FieldDefinition(**field.model_dump())
    db.add(db_field)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Field already exists")
    db.refresh(db_field)
    return db_field

@router.get("/definitions/{entity_type}", response_model=List[schemas.FieldDefinitionOut])
async def list_fields(entity_type: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.FieldDefinition).filter(models.FieldDefinition.entity_type == entity_type).all()


@router.put("/definitions/{field_id}", response_model=schemas.FieldDefinitionOut)
async def update_field(
    field_id: str,
    field: schemas.FieldDefinitionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(field_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid field id")
    db_field = db.query(models.FieldDefinition).filter(models.FieldDefinition.id == uid).first()
    if not db_field:
        raise HTTPException(status_code=404, detail="Field not found")
    for key, value in field.model_dump().items():
        setattr(db_field, key, value)
    db.commit()
    db.refresh(db_field)
    return db_field


@router.delete("/definitions/{field_id}", status_code=204)
async def delete_field(
    field_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(field_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid field id")
    db_field = db.query(models.FieldDefinition).filter(models.FieldDefinition.id == uid).first()
    if not db_field:
        raise HTTPException(status_code=404, detail="Field not found")
    db.delete(db_field)
    db.commit()
    return Response(status_code=204)
