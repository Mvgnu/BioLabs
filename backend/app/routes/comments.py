from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/comments", tags=["comments"])

@router.post("/", response_model=schemas.CommentOut)
async def create_comment(
    comment: schemas.CommentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_comment = models.Comment(**comment.model_dump(), created_by=user.id)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


@router.get("/", response_model=list[schemas.CommentOut])
async def list_comments(
    item_id: UUID | None = None,
    entry_id: UUID | None = None,
    article_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.Comment)
    if item_id:
        q = q.filter(models.Comment.item_id == item_id)
    if entry_id:
        q = q.filter(models.Comment.entry_id == entry_id)
    if article_id:
        q = q.filter(models.Comment.knowledge_article_id == article_id)
    return q.all()


@router.put("/{comment_id}", response_model=schemas.CommentOut)
async def update_comment(
    comment_id: str,
    update: schemas.CommentUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(comment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid comment id")
    comment = db.query(models.Comment).filter(models.Comment.id == uid).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(comment, k, v)
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/{comment_id}")
async def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(comment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid comment id")
    comment = db.query(models.Comment).filter(models.Comment.id == uid).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(comment)
    db.commit()
    return {"detail": "deleted"}
