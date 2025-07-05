from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
import json
from sqlalchemy.orm import Session
import sqlalchemy as sa
from typing import List, Optional
import csv
import io
from uuid import UUID
from datetime import datetime

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas, pubsub, search, barcodes, audit
from ..rbac import check_team_role, ensure_item_access


async def get_item_and_check_permission(
    item_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.InventoryItem:
    try:
        uuid = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id")
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != user.id:
        is_member = (
            db.query(models.TeamMember)
            .filter(
                models.TeamMember.team_id == item.team_id,
                models.TeamMember.user_id == user.id,
            )
            .first()
        )
        if not is_member:
            raise HTTPException(status_code=403, detail="Not authorized")
    return item

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post("/items", response_model=schemas.InventoryItemOut)
async def create_item(
    item: schemas.InventoryItemCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_item = models.InventoryItem(**item.model_dump())
    if db_item.team_id:
        check_team_role(db, user, db_item.team_id, ["owner", "manager", "member"])
    if not db_item.team_id:
        # if team not specified, use user's first team if exists
        membership = user.teams[0] if user.teams else None
        if membership:
            db_item.team_id = membership.team_id
    if not db_item.owner_id:
        db_item.owner_id = user.id
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    audit.log_action(db, str(user.id), "create_item", "inventory", str(db_item.id))
    search.index_item(db_item)
    if db_item.team_id:
        await pubsub.publish_team_event(
            str(db_item.team_id),
            {"type": "item_created", "id": str(db_item.id)},
        )
    return db_item


@router.get("/items", response_model=List[schemas.InventoryItemOut])
async def list_items(
    item_type: Optional[str] = None,
    name: Optional[str] = None,
    barcode: Optional[str] = None,
    status: Optional[str] = None,
    team_id: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    custom: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.InventoryItem)
    if not user.is_admin:
        team_ids = [m.team_id for m in user.teams]
        query = query.filter(
            (models.InventoryItem.owner_id == user.id)
            | (models.InventoryItem.team_id.in_(team_ids))
        )
    if item_type:
        query = query.filter(models.InventoryItem.item_type == item_type)
    if name:
        query = query.filter(models.InventoryItem.name.ilike(f"%{name}%"))
    if barcode:
        query = query.filter(models.InventoryItem.barcode == barcode)
    if status:
        query = query.filter(models.InventoryItem.status == status)
    if team_id:
        try:
            team_uuid = UUID(team_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid team id")
        query = query.filter(models.InventoryItem.team_id == team_uuid)
    if created_from:
        try:
            dt_from = datetime.fromisoformat(created_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid created_from")
        query = query.filter(models.InventoryItem.created_at >= dt_from)
    if created_to:
        try:
            dt_to = datetime.fromisoformat(created_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid created_to")
        query = query.filter(models.InventoryItem.created_at <= dt_to)
    if custom:
        try:
            data = json.loads(custom)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid custom filter")
        query = query.filter(models.InventoryItem.custom_data.contains(data))
    return query.all()


@router.get("/facets", response_model=schemas.InventoryFacets)
async def get_facets(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    team_ids = [m.team_id for m in user.teams]
    query = db.query(models.InventoryItem)
    if not user.is_admin:
        query = query.filter(
            (models.InventoryItem.owner_id == user.id)
            | (models.InventoryItem.team_id.in_(team_ids))
        )
    else:
        # admin can access all teams
        team_ids = [t.id for t in db.query(models.Team.id).all()]
    # Get all item types from the table
    all_types = db.query(models.ItemType).order_by(models.ItemType.name).all()
    # Count usage for each type
    type_counts = dict(
        db.query(models.InventoryItem.item_type, sa.func.count())
        .group_by(models.InventoryItem.item_type)
        .all()
    )
    item_types = [
        schemas.FacetCount(key=it.name, count=type_counts.get(it.name, 0))
        for it in all_types
    ]
    statuses = (
        query.with_entities(models.InventoryItem.status, sa.func.count())
        .group_by(models.InventoryItem.status)
        .all()
    )
    teams = (
        query.with_entities(models.InventoryItem.team_id, sa.func.count())
        .group_by(models.InventoryItem.team_id)
        .all()
    )
    team_names = {
        str(t.id): t.name
        for t in db.query(models.Team).filter(
            models.Team.id.in_([t[0] for t in teams if t[0]])
        ).all()
    }
    fields = (
        db.query(models.FieldDefinition)
        .filter(
            (models.FieldDefinition.team_id.is_(None))
            | (models.FieldDefinition.team_id.in_(team_ids))
        )
        .all()
    )
    return schemas.InventoryFacets(
        item_types=item_types,
        statuses=[schemas.FacetCount(key=st[0], count=st[1]) for st in statuses],
        teams=[
            schemas.FacetCount(
                key=team_names.get(str(t[0]), str(t[0])), count=t[1]
            )
            for t in teams
            if t[0]
        ],
        fields=fields,
    )


@router.get("/export")
async def export_items(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "item_type",
        "name",
        "barcode",
        "status",
    ])
    query = db.query(models.InventoryItem)
    if not user.is_admin:
        team_ids = [m.team_id for m in user.teams]
        query = query.filter(
            (models.InventoryItem.owner_id == user.id)
            | (models.InventoryItem.team_id.in_(team_ids))
        )
    for item in query.all():
        writer.writerow(
            [
                str(item.id),
                item.item_type,
                item.name,
                item.barcode or "",
                item.status,
            ]
        )
    output.seek(0)
    headers = {
        "Content-Disposition": "attachment; filename=inventory.csv"
    }
    return Response(content=output.read(), media_type="text/csv", headers=headers)


@router.post("/import", response_model=List[schemas.InventoryItemOut])
async def import_items(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    data = await file.read()
    reader = csv.DictReader(io.StringIO(data.decode()))
    items: list[models.InventoryItem] = []
    for row in reader:
        try:
            custom = json.loads(row.get("custom_data", "{}"))
        except json.JSONDecodeError:
            custom = {}
        item = models.InventoryItem(
            item_type=row.get("item_type", "sample"),
            name=row.get("name", ""),
            barcode=row.get("barcode") or None,
            status=row.get("status"),
            custom_data=custom,
            owner_id=user.id,
        )
        if user.teams:
            item.team_id = user.teams[0].team_id
        db.add(item)
        items.append(item)
    db.commit()
    for it in items:
        db.refresh(it)
        search.index_item(it)
    return items


@router.put("/items/{item_id}", response_model=schemas.InventoryItemOut)
async def update_item(
    item: schemas.InventoryItemUpdate,
    db_item: models.InventoryItem = Depends(get_item_and_check_permission),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    for key, value in item.model_dump(exclude_unset=True).items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    audit.log_action(db, str(user.id), "update_item", "inventory", str(db_item.id))
    if db_item.team_id:
        await pubsub.publish_team_event(
            str(db_item.team_id),
            {"type": "item_updated", "id": str(db_item.id)},
        )
    return db_item


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    db_item: models.InventoryItem = Depends(get_item_and_check_permission),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db.delete(db_item)
    db.commit()
    audit.log_action(db, str(user.id), "delete_item", "inventory", str(db_item.id))
    search.delete_item(str(db_item.id))
    if db_item.team_id:
        await pubsub.publish_team_event(
            str(db_item.team_id),
            {"type": "item_deleted", "id": str(db_item.id)},
        )
    return Response(status_code=204)


@router.post("/relationships", response_model=schemas.ItemRelationshipOut)
async def create_relationship(
    rel: schemas.ItemRelationshipCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    ensure_item_access(db, user, rel.from_item, roles=("manager", "owner"))
    ensure_item_access(db, user, rel.to_item, roles=("manager", "owner"))
    db_rel = models.ItemRelationship(**rel.model_dump())
    db.add(db_rel)
    db.commit()
    db.refresh(db_rel)
    return db_rel


@router.get(
    "/items/{item_id}/relationships",
    response_model=List[schemas.ItemRelationshipOut],
)
async def list_relationships(
    item_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        item_uuid = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id")
    ensure_item_access(db, user, item_uuid)
    return (
        db.query(models.ItemRelationship)
        .filter(
            (models.ItemRelationship.from_item == item_uuid)
            | (models.ItemRelationship.to_item == item_uuid)
        )
        .all()
    )


@router.get("/items/{item_id}/graph", response_model=schemas.ItemGraphOut)
async def relationship_graph(
    item_id: str,
    depth: int = 1,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        start_id = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id")
    ensure_item_access(db, user, start_id)

    visited = set()
    nodes = []
    edges = []
    queue = [(start_id, 0)]
    while queue:
        current_id, level = queue.pop(0)
        if current_id in visited or level > depth:
            continue
        visited.add(current_id)
        item = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id == current_id)
            .first()
        )
        if item:
            nodes.append(item)
        rels = (
            db.query(models.ItemRelationship)
            .filter(
                (models.ItemRelationship.from_item == current_id)
                | (models.ItemRelationship.to_item == current_id)
            )
            .all()
        )
        for rel in rels:
            edges.append(rel)
            other_id = rel.to_item if rel.from_item == current_id else rel.from_item
            if other_id not in visited:
                queue.append((other_id, level + 1))

    return {"nodes": nodes, "edges": edges}


@router.post("/items/{item_id}/barcode")
async def generate_barcode(
    item_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        item_uuid = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id")
    item = ensure_item_access(db, user, item_uuid, roles=("manager", "owner"))
    if not item.barcode:
        code = barcodes.generate_unique_code()
        while db.query(models.InventoryItem).filter(models.InventoryItem.barcode == code).first():
            code = barcodes.generate_unique_code()
        item.barcode = code
        db.commit()
        db.refresh(item)
    img = barcodes.generate_barcode_png(item.barcode)
    return Response(content=img, media_type="image/png")


@router.post("/bulk/update", response_model=schemas.BulkOperationResponse)
async def bulk_update_items(
    request: schemas.BulkUpdateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    results = []
    successful = 0
    failed = 0
    
    for item_update in request.items:
        try:
            # Check permissions
            item = ensure_item_access(db, user, item_update.id, roles=("manager", "owner"))
            
            # Apply updates
            for key, value in item_update.data.model_dump(exclude_unset=True).items():
                setattr(item, key, value)
            
            db.commit()
            db.refresh(item)
            
            # Audit and search indexing
            audit.log_action(db, str(user.id), "bulk_update_item", "inventory", str(item.id))
            search.index_item(item)
            
            # Publish team event if applicable
            if item.team_id:
                await pubsub.publish_team_event(
                    str(item.team_id),
                    {"type": "item_updated", "id": str(item.id)},
                )
            
            results.append(schemas.BulkOperationResult(
                success=True,
                item_id=item_update.id
            ))
            successful += 1
            
        except Exception as e:
            db.rollback()
            results.append(schemas.BulkOperationResult(
                success=False,
                item_id=item_update.id,
                error=str(e)
            ))
            failed += 1
    
    return schemas.BulkOperationResponse(
        results=results,
        total=len(request.items),
        successful=successful,
        failed=failed
    )


@router.post("/bulk/delete", response_model=schemas.BulkOperationResponse)
async def bulk_delete_items(
    request: schemas.BulkDeleteRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    results = []
    successful = 0
    failed = 0
    
    for item_id in request.item_ids:
        try:
            # Check permissions
            item = ensure_item_access(db, user, item_id, roles=("manager", "owner"))
            
            # Delete item
            db.delete(item)
            db.commit()
            
            # Audit and search cleanup
            audit.log_action(db, str(user.id), "bulk_delete_item", "inventory", str(item_id))
            search.delete_item(str(item_id))
            
            # Publish team event if applicable
            if item.team_id:
                await pubsub.publish_team_event(
                    str(item.team_id),
                    {"type": "item_deleted", "id": str(item_id)},
                )
            
            results.append(schemas.BulkOperationResult(
                success=True,
                item_id=item_id
            ))
            successful += 1
            
        except Exception as e:
            db.rollback()
            results.append(schemas.BulkOperationResult(
                success=False,
                item_id=item_id,
                error=str(e)
            ))
            failed += 1
    
    return schemas.BulkOperationResponse(
        results=results,
        total=len(request.item_ids),
        successful=successful,
        failed=failed
    )


@router.get("/item-types", response_model=List[schemas.ItemTypeOut])
async def list_item_types(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.ItemType).order_by(models.ItemType.name).all()

@router.post("/item-types", response_model=schemas.ItemTypeOut)
async def create_item_type(
    item_type: schemas.ItemTypeCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    # Only allow admin or manager roles to create types (optional, can be relaxed)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    if db.query(models.ItemType).filter_by(name=item_type.name).first():
        raise HTTPException(status_code=400, detail="Item type already exists")
    db_type = models.ItemType(**item_type.model_dump())
    db.add(db_type)
    db.commit()
    db.refresh(db_type)
    return db_type
