from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas
from .files import MINIO_ENDPOINT, minio_client, UPLOAD_DIR, MINIO_BUCKET
import os, io
from uuid import uuid4
from fastapi import UploadFile, File

router = APIRouter(prefix="/api/services", tags=["services"])


@router.post("/listings", response_model=schemas.ServiceListingOut)
def create_service_listing(
    data: schemas.ServiceListingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    listing = models.ServiceListing(
        provider_id=user.id,
        name=data.name,
        description=data.description,
        price=data.price,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/listings", response_model=List[schemas.ServiceListingOut])
def list_service_listings(db: Session = Depends(get_db)):
    return (
        db.query(models.ServiceListing)
        .filter(models.ServiceListing.status == "open")
        .all()
    )


@router.post(
    "/listings/{listing_id}/requests",
    response_model=schemas.ServiceRequestOut,
)
def create_service_request(
    listing_id: UUID,
    data: schemas.ServiceRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    listing = db.get(models.ServiceListing, listing_id)
    if not listing or listing.status != "open":
        raise HTTPException(status_code=404)
    req = models.ServiceRequest(
        listing_id=listing_id,
        requester_id=user.id,
        item_id=data.item_id,
        message=data.message,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get(
    "/listings/{listing_id}/requests",
    response_model=List[schemas.ServiceRequestOut],
)
def list_service_requests(
    listing_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    listing = db.get(models.ServiceListing, listing_id)
    if not listing or listing.provider_id != user.id:
        raise HTTPException(status_code=403)
    return (
        db.query(models.ServiceRequest)
        .filter_by(listing_id=listing_id)
        .all()
    )


@router.post(
    "/requests/{request_id}/accept",
    response_model=schemas.ServiceRequestOut,
)
def accept_service_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(models.ServiceRequest, request_id)
    if not req:
        raise HTTPException(status_code=404)
    listing = db.get(models.ServiceListing, req.listing_id)
    if listing.provider_id != user.id:
        raise HTTPException(status_code=403)
    req.status = "accepted"
    listing.status = "closed"
    db.commit()
    db.refresh(req)
    return req


@router.post(
    "/requests/{request_id}/reject",
    response_model=schemas.ServiceRequestOut,
)
def reject_service_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(models.ServiceRequest, request_id)
    if not req:
        raise HTTPException(status_code=404)
    listing = db.get(models.ServiceListing, req.listing_id)
    if listing.provider_id != user.id:
        raise HTTPException(status_code=403)
    req.status = "rejected"
    db.commit()
    db.refresh(req)
    return req


@router.post("/requests/{request_id}/deliver", response_model=schemas.ServiceRequestOut)
async def deliver_service_result(
    request_id: UUID,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(models.ServiceRequest, request_id)
    if not req:
        raise HTTPException(status_code=404)
    listing = db.get(models.ServiceListing, req.listing_id)
    if listing.provider_id != user.id:
        raise HTTPException(status_code=403)

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
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        save_path = os.path.join(UPLOAD_DIR, object_name)
        with open(save_path, "wb") as f:
            f.write(data)
        storage_path = save_path
        file_size = upload.size or 0

    db_file = models.File(
        id=file_id,
        item_id=req.item_id,
        filename=upload.filename,
        file_type=upload.content_type or "application/octet-stream",
        file_size=file_size,
        storage_path=storage_path,
        uploaded_by=user.id,
    )
    db.add(db_file)
    req.result_file_id = file_id
    req.status = "completed"
    db.commit()
    db.refresh(req)
    return req


@router.post("/requests/{request_id}/confirm-payment", response_model=schemas.ServiceRequestOut)
def confirm_payment(
    request_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(models.ServiceRequest, request_id)
    if not req:
        raise HTTPException(status_code=404)
    if req.requester_id != user.id:
        raise HTTPException(status_code=403)
    req.payment_status = "paid"
    db.commit()
    db.refresh(req)
    return req
