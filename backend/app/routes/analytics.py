from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/summary", response_model=List[schemas.ItemTypeCount])
def analytics_summary(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.InventoryItem.item_type, func.count(models.InventoryItem.id))
        .filter(models.InventoryItem.team_id == user.team_id)
        .group_by(models.InventoryItem.item_type)
        .all()
    )
    return [{"item_type": r[0], "count": r[1]} for r in rows]


@router.get("/trending-protocols", response_model=List[schemas.TrendingProtocol])
def analytics_trending_protocols(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            models.ProtocolExecution.template_id,
            func.count(models.ProtocolExecution.id).label("cnt"),
            func.max(models.ProtocolExecution.created_at).label("last"),
        )
        .join(models.ProtocolTemplate, models.ProtocolExecution.template_id == models.ProtocolTemplate.id)
        .filter(models.ProtocolExecution.created_at >= since)
        .filter(models.ProtocolTemplate.team_id == user.team_id)
        .group_by(models.ProtocolExecution.template_id)
        .all()
    )
    scored = [
        (
            r.template_id,
            r.cnt,
            r.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - r.last.replace(tzinfo=timezone.utc)
                ).days
            ),
        )
        for r in rows
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    template_ids = [r[0] for r in scored]
    templates = {
        t.id: t
        for t in db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id.in_(template_ids)).all()
    }
    return [
        {
            "template_id": tid,
            "template_name": templates.get(tid).name if tid in templates else "",
            "count": cnt,
        }
        for tid, cnt, _score in scored[:5]
    ]


@router.get("/trending-protocol-stars", response_model=List[schemas.TrendingProtocol])
def analytics_trending_protocol_stars(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            models.ProtocolStar.protocol_id,
            func.count(models.ProtocolStar.user_id).label("cnt"),
            func.max(models.ProtocolStar.created_at).label("last"),
        )
        .filter(models.ProtocolStar.created_at >= since)
        .group_by(models.ProtocolStar.protocol_id)
        .all()
    )
    scored = [
        (
            r.protocol_id,
            r.cnt,
            r.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - r.last.replace(tzinfo=timezone.utc)
                ).days
            ),
        )
        for r in rows
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    ids = [r[0] for r in scored]
    templates = {
        t.id: t
        for t in db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id.in_(ids)).all()
    }
    return [
        {
            "template_id": tid,
            "template_name": templates.get(tid).name if tid in templates else "",
            "count": cnt,
        }
        for tid, cnt, _ in scored[:5]
    ]


@router.get("/trending-article-stars", response_model=List[schemas.TrendingArticle])
def analytics_trending_article_stars(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            models.KnowledgeArticleStar.article_id,
            func.count(models.KnowledgeArticleStar.user_id).label("cnt"),
            func.max(models.KnowledgeArticleStar.created_at).label("last"),
        )
        .filter(models.KnowledgeArticleStar.created_at >= since)
        .group_by(models.KnowledgeArticleStar.article_id)
        .all()
    )
    scored = [
        (
            r.article_id,
            r.cnt,
            r.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - r.last.replace(tzinfo=timezone.utc)
                ).days
            ),
        )
        for r in rows
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    ids = [r[0] for r in scored]
    arts = {
        a.id: a
        for a in db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id.in_(ids)).all()
    }
    return [
        {
            "article_id": aid,
            "title": arts.get(aid).title if aid in arts else "",
            "count": cnt,
        }
        for aid, cnt, _ in scored[:5]
    ]


@router.get("/trending-article-comments", response_model=List[schemas.TrendingArticle])
def analytics_trending_article_comments(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            models.Comment.knowledge_article_id,
            func.count(models.Comment.id).label("cnt"),
            func.max(models.Comment.created_at).label("last"),
        )
        .filter(
            models.Comment.knowledge_article_id.isnot(None),
            models.Comment.created_at >= since,
        )
        .group_by(models.Comment.knowledge_article_id)
        .all()
    )
    scored = [
        (
            r.knowledge_article_id,
            r.cnt,
            r.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - r.last.replace(tzinfo=timezone.utc)
                ).days
            ),
        )
        for r in rows
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    ids = [r[0] for r in scored]
    arts = {
        a.id: a
        for a in db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id.in_(ids)).all()
    }
    return [
        {
            "article_id": aid,
            "title": arts.get(aid).title if aid in arts else "",
            "count": cnt,
        }
        for aid, cnt, _ in scored[:5]
    ]


@router.get("/trending-articles", response_model=List[schemas.TrendingArticle])
def analytics_trending_articles(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            models.KnowledgeArticleView.article_id,
            func.count(models.KnowledgeArticleView.id).label("cnt"),
            func.max(models.KnowledgeArticleView.viewed_at).label("last"),
        )
        .join(models.KnowledgeArticle, models.KnowledgeArticleView.article_id == models.KnowledgeArticle.id)
        .filter(models.KnowledgeArticleView.viewed_at >= since)
        .filter(models.KnowledgeArticle.team_id == user.team_id)
        .group_by(models.KnowledgeArticleView.article_id)
        .all()
    )
    scored = [
        (
            r.article_id,
            r.cnt,
            r.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - r.last.replace(tzinfo=timezone.utc)
                ).days
            ),
        )
        for r in rows
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    ids = [r[0] for r in scored]
    arts = {a.id: a for a in db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id.in_(ids)).all()}
    return [
        {
            "article_id": aid,
            "title": arts.get(aid).title if aid in arts else "",
            "count": cnt,
        }
        for aid, cnt, _score in scored[:5]
    ]


@router.get("/trending-items", response_model=List[schemas.TrendingItem])
def analytics_trending_items(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            models.NotebookEntry.item_id,
            func.count(models.NotebookEntry.id).label("cnt"),
            func.max(models.NotebookEntry.created_at).label("last"),
        )
        .join(models.InventoryItem, models.NotebookEntry.item_id == models.InventoryItem.id)
        .filter(
            models.NotebookEntry.item_id.isnot(None),
            models.NotebookEntry.created_at >= since,
            models.InventoryItem.team_id == user.team_id
        )
        .group_by(models.NotebookEntry.item_id)
        .all()
    )
    scored = [
        (
            r.item_id,
            r.cnt,
            r.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - r.last.replace(tzinfo=timezone.utc)
                ).days
            ),
        )
        for r in rows
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    ids = [r[0] for r in scored]
    items = {
        i.id: i
        for i in db.query(models.InventoryItem).filter(models.InventoryItem.id.in_(ids)).all()
    }
    return [
        {
            "item_id": iid,
            "name": items.get(iid).name if iid in items else "",
            "count": cnt,
        }
        for iid, cnt, _score in scored[:5]
    ]


@router.get("/trending-threads", response_model=List[schemas.TrendingThread])
def analytics_trending_threads(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            models.ForumPost.thread_id,
            func.count(models.ForumPost.id).label("cnt"),
            func.max(models.ForumPost.created_at).label("last"),
        )
        .join(models.ForumThread, models.ForumPost.thread_id == models.ForumThread.id)
        .filter(models.ForumPost.created_at >= since)
        .filter(models.ForumThread.team_id == user.team_id)
        .group_by(models.ForumPost.thread_id)
        .all()
    )
    scored = [
        (
            r.thread_id,
            r.cnt,
            r.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - r.last.replace(tzinfo=timezone.utc)
                ).days
            ),
            r.last,
        )
        for r in rows
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    ids = [r[0] for r in scored]
    threads = {
        t.id: t
        for t in db.query(models.ForumThread).filter(models.ForumThread.id.in_(ids)).all()
    }
    return [
        {
            "thread_id": tid,
            "title": threads.get(tid).title if tid in threads else "",
            "count": cnt,
        }
        for tid, cnt, _score, _last in scored[:5]
    ]


@router.get("/trending-posts", response_model=List[schemas.TrendingPost])
def analytics_trending_posts(
    days: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    likes = (
        db.query(
            models.PostLike.post_id,
            func.count(models.PostLike.user_id).label("cnt"),
        )
        .filter(models.PostLike.created_at >= since)
        .group_by(models.PostLike.post_id)
        .all()
    )
    ids = [l.post_id for l in likes]
    posts = {
        p.id: p
        for p in db.query(models.Post).filter(models.Post.id.in_(ids)).all()
    }
    scored = [
        (
            l.post_id,
            l.cnt,
            l.cnt
            / (
                1
                + (
                    datetime.now(timezone.utc)
                    - posts[l.post_id].created_at.replace(tzinfo=timezone.utc)
                ).days
            ),
        )
        for l in likes
        if l.post_id in posts
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    return [
        {
            "post_id": pid,
            "content": posts[pid].content,
            "count": cnt,
        }
        for pid, cnt, _score in scored[:5]
    ]
