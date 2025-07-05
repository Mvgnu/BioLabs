from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session
import os
from uuid import uuid4, UUID
import io

from minio import Minio
from fastapi.responses import StreamingResponse

from ..sequence import parse_chromatogram, process_sequence_file

from ..database import get_db
from ..auth import get_current_user
from ..rbac import ensure_item_access
from .. import models, schemas

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploaded_files")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "uploads")

# Only initialize MinIO client if all required environment variables are set
if MINIO_ENDPOINT and MINIO_ACCESS_KEY and MINIO_SECRET_KEY and MINIO_ENDPOINT.strip():
    try:
        minio_client = Minio(
            MINIO_ENDPOINT.strip(),
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_ENDPOINT.strip().startswith("https"),
        )
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
    except Exception as e:
        print(f"Failed to initialize MinIO client: {e}")
        minio_client = None
else:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    minio_client = None

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=schemas.FileOut)
async def upload_file(
    item_id: str = Form(...),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        item_uuid = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id")
    item = ensure_item_access(db, user, item_uuid)

    file_id = uuid4()
    safe_name = os.path.basename(upload.filename)
    object_name = f"{file_id}_{safe_name}"
    data = await upload.read()
    if MINIO_ENDPOINT:
        minio_client.put_object(
            MINIO_BUCKET,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=upload.content_type or "application/octet-stream",
        )
        storage_path = f"s3://{MINIO_BUCKET}/{object_name}"
        file_size = len(data)
    else:
        save_path = os.path.join(UPLOAD_DIR, object_name)
        with open(save_path, "wb") as f:
            f.write(data)
        storage_path = save_path
        file_size = upload.size or 0

    db_file = models.File(
        id=file_id,
        item_id=item_uuid,
        filename=upload.filename,
        file_type=upload.content_type or "application/octet-stream",
        file_size=file_size,
        storage_path=storage_path,
        uploaded_by=user.id,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


@router.get("/items/{item_id}", response_model=list[schemas.FileOut])
async def list_files(
    item_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        item_uuid = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id")
    ensure_item_access(db, user, item_uuid)
    return db.query(models.File).filter(models.File.item_id == item_uuid).all()


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        file_uuid = UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file id")
    db_file = db.query(models.File).filter(models.File.id == file_uuid).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    ensure_item_access(db, user, db_file.item_id)
    if MINIO_ENDPOINT:
        data = minio_client.get_object(MINIO_BUCKET, db_file.storage_path.split("/")[-1]).read()
    else:
        with open(db_file.storage_path, "rb") as fh:
            data = fh.read()
    return StreamingResponse(io.BytesIO(data), media_type=db_file.file_type, headers={"Content-Disposition": f"attachment; filename={db_file.filename}"})


@router.get("/{file_id}/chromatogram", response_model=schemas.ChromatogramOut)
async def file_chromatogram(
    file_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        file_uuid = UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file id")
    db_file = db.query(models.File).filter(models.File.id == file_uuid).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    ensure_item_access(db, user, db_file.item_id)
    if MINIO_ENDPOINT:
        data = minio_client.get_object(MINIO_BUCKET, db_file.storage_path.split("/")[-1]).read()
    else:
        with open(db_file.storage_path, "rb") as fh:
            data = fh.read()
    try:
        return parse_chromatogram(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid chromatogram file")


@router.get("/{file_id}/sequence", response_model=list[schemas.SequenceRead])
async def file_sequence(
    file_id: str,
    format: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        file_uuid = UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file id")
    db_file = db.query(models.File).filter(models.File.id == file_uuid).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    ensure_item_access(db, user, db_file.item_id)
    if MINIO_ENDPOINT:
        data = minio_client.get_object(MINIO_BUCKET, db_file.storage_path.split("/")[-1]).read()
    else:
        with open(db_file.storage_path, "rb") as fh:
            data = fh.read()
    fmt = format
    if not fmt:
        ext = db_file.filename.rsplit(".", 1)[-1].lower()
        if ext in {"fastq", "fq"}:
            fmt = "fastq"
        else:
            fmt = "fasta"
    try:
        return process_sequence_file(data, fmt)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid sequence file")
