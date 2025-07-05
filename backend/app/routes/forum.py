from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/forum", tags=["forum"])


@router.post("/threads", response_model=schemas.ForumThreadOut)
async def create_thread(
    thread: schemas.ForumThreadCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_thread = models.ForumThread(title=thread.title, created_by=user.id)
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread


@router.get("/threads", response_model=list[schemas.ForumThreadOut])
async def list_threads(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.ForumThread).all()


@router.post("/threads/{thread_id}/posts", response_model=schemas.ForumPostOut)
async def create_post(
    thread_id: str,
    post: schemas.ForumPostCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        tid = UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread id")
    if not db.query(models.ForumThread).filter(models.ForumThread.id == tid).first():
        raise HTTPException(status_code=404, detail="Thread not found")
    db_post = models.ForumPost(thread_id=tid, user_id=user.id, content=post.content)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post


@router.get("/threads/{thread_id}/posts", response_model=list[schemas.ForumPostOut])
async def list_posts(
    thread_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        tid = UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread id")
    return db.query(models.ForumPost).filter(models.ForumPost.thread_id == tid).all()
