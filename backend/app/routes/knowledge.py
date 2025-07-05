from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/articles", response_model=schemas.KnowledgeArticleOut)
async def create_article(
    article: schemas.KnowledgeArticleCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_article = models.KnowledgeArticle(
        **article.model_dump(exclude_unset=True), created_by=user.id
    )
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article


@router.get("/articles", response_model=list[schemas.KnowledgeArticleOut])
async def list_articles(
    tag: str | None = None,
    public_only: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.KnowledgeArticle)
    if tag:
        query = query.filter(models.KnowledgeArticle.tags.contains([tag]))
    if public_only:
        query = query.filter(models.KnowledgeArticle.is_public == True)
    return query.all()


@router.get("/articles/{article_id}", response_model=schemas.KnowledgeArticleOut)
async def get_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    art = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == uid).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    if not art.is_public and art.created_by != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.add(models.KnowledgeArticleView(article_id=uid, user_id=user.id))
    db.commit()
    return art


@router.put("/articles/{article_id}", response_model=schemas.KnowledgeArticleOut)
async def update_article(
    article_id: str,
    update: schemas.KnowledgeArticleUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    art = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == uid).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    if art.created_by != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(art, key, value)
    db.commit()
    db.refresh(art)
    return art


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    art = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == uid).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    if art.created_by != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(art)
    db.commit()
    return {"detail": "deleted"}


@router.post("/articles/{article_id}/view")
async def record_article_view(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    article = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == uid).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    db.add(models.KnowledgeArticleView(article_id=uid, user_id=user.id))
    db.commit()
    return {"detail": "view recorded"}


@router.post("/articles/{article_id}/star", response_model=schemas.KnowledgeArticleStarOut)
async def star_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    article = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == uid).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    existing = (
        db.query(models.KnowledgeArticleStar)
        .filter(models.KnowledgeArticleStar.article_id == uid, models.KnowledgeArticleStar.user_id == user.id)
        .first()
    )
    if existing:
        return existing
    star = models.KnowledgeArticleStar(article_id=uid, user_id=user.id)
    db.add(star)
    db.commit()
    db.refresh(star)
    return star


@router.delete("/articles/{article_id}/star")
async def unstar_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    star = (
        db.query(models.KnowledgeArticleStar)
        .filter(models.KnowledgeArticleStar.article_id == uid, models.KnowledgeArticleStar.user_id == user.id)
        .first()
    )
    if star:
        db.delete(star)
        db.commit()
    return {"detail": "ok"}


@router.get("/articles/{article_id}/stars")
async def get_article_stars(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    count = db.query(models.KnowledgeArticleStar).filter(models.KnowledgeArticleStar.article_id == uid).count()
    return {"count": count}
