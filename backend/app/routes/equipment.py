from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


@router.post("/devices", response_model=schemas.EquipmentOut)
def create_equipment(
    equipment: schemas.EquipmentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_eq = models.Equipment(**equipment.model_dump(), created_by=user.id)
    db.add(db_eq)
    db.commit()
    db.refresh(db_eq)
    return db_eq


@router.get("/devices", response_model=list[schemas.EquipmentOut])
def list_equipment(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Equipment).all()


@router.put("/devices/{equipment_id}", response_model=schemas.EquipmentOut)
def update_equipment(
    equipment_id: UUID,
    data: schemas.EquipmentUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    eq = db.get(models.Equipment, equipment_id)
    if not eq:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(eq, k, v)
    db.commit()
    db.refresh(eq)
    return eq


@router.post("/devices/{equipment_id}/readings", response_model=schemas.EquipmentReadingOut)
def add_reading(
    equipment_id: UUID,
    reading: schemas.EquipmentReadingCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    eq = db.get(models.Equipment, equipment_id)
    if not eq:
        raise HTTPException(status_code=404)
    r = models.EquipmentReading(equipment_id=equipment_id, data=reading.data)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.get("/devices/{equipment_id}/readings", response_model=list[schemas.EquipmentReadingOut])
def list_readings(
    equipment_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.EquipmentReading).filter_by(equipment_id=equipment_id).all()


@router.post("/maintenance", response_model=schemas.EquipmentMaintenanceOut)
def create_maintenance(
    task: schemas.EquipmentMaintenanceCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    eq = db.get(models.Equipment, task.equipment_id)
    if not eq:
        raise HTTPException(status_code=404)
    obj = models.EquipmentMaintenance(**task.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/maintenance", response_model=list[schemas.EquipmentMaintenanceOut])
def list_maintenance(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.EquipmentMaintenance).all()


@router.put("/maintenance/{task_id}", response_model=schemas.EquipmentMaintenanceOut)
def update_maintenance(
    task_id: UUID,
    data: schemas.EquipmentMaintenanceCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    obj = db.get(models.EquipmentMaintenance, task_id)
    if not obj:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/sops", response_model=schemas.SOPOut)
def create_sop(
    sop: schemas.SOPCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    obj = models.SOP(**sop.model_dump(), created_by=user.id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/sops", response_model=list[schemas.SOPOut])
def list_sops(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.SOP).all()


@router.post("/training", response_model=schemas.TrainingRecordOut)
def create_training(
    rec: schemas.TrainingRecordCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    obj = models.TrainingRecord(**rec.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/training", response_model=list[schemas.TrainingRecordOut])
def list_training(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.TrainingRecord).all()
