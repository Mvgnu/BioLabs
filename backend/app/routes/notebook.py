from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
from fpdf import FPDF

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/notebook", tags=["notebook"])

@router.post("/entries", response_model=schemas.NotebookEntryOut)
async def create_entry(
    entry: schemas.NotebookEntryCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    data = entry.model_dump()
    data["items"] = [str(i) for i in data.get("items", [])]
    data["protocols"] = [str(p) for p in data.get("protocols", [])]
    data["images"] = [str(img) for img in data.get("images", [])]
    data["blocks"] = data.get("blocks", [])
    db_entry = models.NotebookEntry(**data, created_by=user.id)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    version = models.NotebookEntryVersion(
        entry_id=db_entry.id,
        title=db_entry.title,
        content=db_entry.content,
        blocks=db_entry.blocks,
        created_by=user.id,
    )
    db.add(version)
    db.commit()
    return db_entry

@router.get("/entries", response_model=list[schemas.NotebookEntryOut])
async def list_entries(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.NotebookEntry).all()

@router.get("/entries/{entry_id}", response_model=schemas.NotebookEntryOut)
async def get_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry id")
    entry = db.query(models.NotebookEntry).filter(models.NotebookEntry.id == uid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry

@router.get("/entries/{entry_id}/export")
async def export_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry id")
    entry = (
        db.query(models.NotebookEntry)
        .filter(models.NotebookEntry.id == uid)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=entry.title, ln=True)
    pdf.multi_cell(0, 10, entry.content)
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")
    else:
        pdf_bytes = bytes(pdf_bytes)
    return Response(content=pdf_bytes, media_type="application/pdf")

@router.put("/entries/{entry_id}", response_model=schemas.NotebookEntryOut)
async def update_entry(
    entry_id: str,
    update: schemas.NotebookEntryUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry id")
    entry = db.query(models.NotebookEntry).filter(models.NotebookEntry.id == uid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.is_locked:
        raise HTTPException(status_code=400, detail="Entry is locked")
    upd = update.model_dump(exclude_unset=True)
    if "items" in upd:
        upd["items"] = [str(i) for i in upd["items"]]
    if "protocols" in upd:
        upd["protocols"] = [str(p) for p in upd["protocols"]]
    if "images" in upd:
        upd["images"] = [str(img) for img in upd["images"]]
    if "blocks" in upd:
        upd["blocks"] = upd["blocks"]
    for k, v in upd.items():
        setattr(entry, k, v)
    db.commit()
    version = models.NotebookEntryVersion(
        entry_id=entry.id,
        title=entry.title,
        content=entry.content,
        blocks=entry.blocks,
        created_by=user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry id")
    entry = db.query(models.NotebookEntry).filter(models.NotebookEntry.id == uid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"detail": "deleted"}


@router.post("/entries/{entry_id}/sign", response_model=schemas.NotebookEntryOut)
async def sign_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry id")
    entry = db.query(models.NotebookEntry).filter(models.NotebookEntry.id == uid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.is_locked:
        raise HTTPException(status_code=400, detail="Entry already signed")
    if entry.created_by != user.id:
        raise HTTPException(status_code=403, detail="Only the author may sign")
    entry.is_locked = True
    entry.signed_by = user.id
    entry.signed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry


@router.post(
    "/entries/{entry_id}/witness",
    response_model=schemas.NotebookEntryOut,
)
async def witness_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry id")
    entry = db.query(models.NotebookEntry).filter(models.NotebookEntry.id == uid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if not entry.is_locked:
        raise HTTPException(status_code=400, detail="Entry must be signed first")
    if entry.witness_id is not None:
        raise HTTPException(status_code=400, detail="Already witnessed")
    if entry.created_by == user.id:
        raise HTTPException(status_code=400, detail="Author cannot witness")
    entry.witness_id = user.id
    entry.witnessed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry


@router.get(
    "/entries/{entry_id}/versions",
    response_model=list[schemas.NotebookEntryVersionOut],
)
async def list_versions(
    entry_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry id")
    versions = (
        db.query(models.NotebookEntryVersion)
        .filter(models.NotebookEntryVersion.entry_id == uid)
        .order_by(models.NotebookEntryVersion.created_at)
        .all()
    )
    return versions
