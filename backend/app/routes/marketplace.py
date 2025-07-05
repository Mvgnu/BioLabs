from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

@router.post("/listings", response_model=schemas.MarketplaceListingOut)
def create_listing(
    data: schemas.MarketplaceListingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    item = db.get(models.InventoryItem, data.item_id)
    if not item or (item.owner_id and item.owner_id != user.id):
        raise HTTPException(status_code=403)
    listing = models.MarketplaceListing(
        item_id=item.id,
        seller_id=user.id,
        price=data.price,
        description=data.description,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/listings", response_model=List[schemas.MarketplaceListingOut])
def list_listings(db: Session = Depends(get_db)):
    return (
        db.query(models.MarketplaceListing)
        .filter(models.MarketplaceListing.status == "open")
        .all()
    )


@router.post(
    "/listings/{listing_id}/requests",
    response_model=schemas.MarketplaceRequestOut,
)
def create_request(
    listing_id: UUID,
    data: schemas.MarketplaceRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    listing = db.get(models.MarketplaceListing, listing_id)
    if not listing or listing.status != "open":
        raise HTTPException(status_code=404)
    req = models.MarketplaceRequest(
        listing_id=listing_id,
        buyer_id=user.id,
        message=data.message,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get(
    "/listings/{listing_id}/requests",
    response_model=List[schemas.MarketplaceRequestOut],
)
def list_requests(
    listing_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    listing = db.get(models.MarketplaceListing, listing_id)
    if not listing or listing.seller_id != user.id:
        raise HTTPException(status_code=403)
    return (
        db.query(models.MarketplaceRequest)
        .filter_by(listing_id=listing_id)
        .all()
    )


@router.post(
    "/requests/{request_id}/accept",
    response_model=schemas.MarketplaceRequestOut,
)
def accept_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(models.MarketplaceRequest, request_id)
    if not req:
        raise HTTPException(status_code=404)
    listing = db.get(models.MarketplaceListing, req.listing_id)
    if listing.seller_id != user.id:
        raise HTTPException(status_code=403)
    req.status = "accepted"
    listing.status = "closed"
    db.commit()
    db.refresh(req)
    return req


@router.post(
    "/requests/{request_id}/reject",
    response_model=schemas.MarketplaceRequestOut,
)
def reject_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(models.MarketplaceRequest, request_id)
    if not req:
        raise HTTPException(status_code=404)
    listing = db.get(models.MarketplaceListing, req.listing_id)
    if listing.seller_id != user.id:
        raise HTTPException(status_code=403)
    req.status = "rejected"
    db.commit()
    db.refresh(req)
    return req
