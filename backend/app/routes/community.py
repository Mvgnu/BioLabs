from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/community", tags=["community"])

@router.post("/posts", response_model=schemas.PostOut)
async def create_post(
    post: schemas.PostCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_post = models.Post(content=post.content, user_id=user.id)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        pid = UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post id")
    post = db.query(models.Post).filter(models.Post.id == pid).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    db.delete(post)
    db.commit()
    return {"detail": "deleted"}


@router.get("/posts", response_model=list[schemas.PostOut])
async def list_posts(
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Post)
    if user_id:
        try:
            uid = UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user id")
        query = query.filter(models.Post.user_id == uid)
    return query.order_by(models.Post.created_at.desc()).all()


@router.post("/follow/{user_id}", response_model=schemas.FollowOut)
async def follow_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")
    if uid == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    follow = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.followed_id == uid,
    ).first()
    if not follow:
        follow = models.Follow(follower_id=current_user.id, followed_id=uid)
        db.add(follow)
        db.commit()
    return follow


@router.delete("/follow/{user_id}")
async def unfollow_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")
    follow = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.followed_id == uid,
    ).first()
    if follow:
        db.delete(follow)
        db.commit()
    return {"detail": "unfollowed"}


@router.get("/feed", response_model=list[schemas.PostOut])
async def get_feed(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    followed_ids = [
        f.followed_id
        for f in db.query(models.Follow).filter(models.Follow.follower_id == current_user.id)
    ]
    if not followed_ids:
        return []
    return (
        db.query(models.Post)
        .filter(models.Post.user_id.in_(followed_ids))
        .order_by(models.Post.created_at.desc())
        .all()
    )


@router.post("/posts/{post_id}/like", response_model=schemas.PostLikeOut)
async def like_post(
    post_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        pid = UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post id")
    if not db.query(models.Post).filter(models.Post.id == pid).first():
        raise HTTPException(status_code=404, detail="Post not found")
    like = (
        db.query(models.PostLike)
        .filter(models.PostLike.post_id == pid, models.PostLike.user_id == user.id)
        .first()
    )
    if not like:
        like = models.PostLike(post_id=pid, user_id=user.id)
        db.add(like)
        db.commit()
    return like


@router.delete("/posts/{post_id}/like")
async def unlike_post(
    post_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        pid = UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post id")
    like = (
        db.query(models.PostLike)
        .filter(models.PostLike.post_id == pid, models.PostLike.user_id == user.id)
        .first()
    )
    if like:
        db.delete(like)
        db.commit()
    return {"detail": "unliked"}


@router.get("/posts/{post_id}/likes", response_model=int)
async def count_likes(
    post_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        pid = UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post id")
    return (
        db.query(models.PostLike)
        .filter(models.PostLike.post_id == pid)
        .count()
    )


@router.post("/posts/{post_id}/report", response_model=schemas.PostReportOut)
async def report_post(
    post_id: str,
    report: schemas.PostReportCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        pid = UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post id")
    post = db.query(models.Post).filter(models.Post.id == pid).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db_report = models.PostReport(post_id=pid, reporter_id=user.id, reason=report.reason)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


@router.get("/reports", response_model=list[schemas.PostReportOut])
async def list_reports(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.PostReport).order_by(models.PostReport.created_at.desc()).all()


@router.post("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        rid = UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report id")
    rep = db.query(models.PostReport).filter(models.PostReport.id == rid).first()
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    rep.status = "resolved"
    db.commit()
    return {"detail": "resolved"}
