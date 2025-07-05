from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/troubleshooting", tags=["troubleshooting"])


@router.post("/articles", response_model=schemas.TroubleshootingArticleOut)
async def create_article(
    article: schemas.TroubleshootingArticleCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_article = models.TroubleshootingArticle(**article.model_dump(), created_by=user.id)
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article


@router.get("/articles", response_model=list[schemas.TroubleshootingArticleOut])
async def list_articles(
    category: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.TroubleshootingArticle)
    if category:
        query = query.filter(models.TroubleshootingArticle.category == category)
    return query.all()


@router.get("/articles/{article_id}", response_model=schemas.TroubleshootingArticleOut)
async def get_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    art = db.query(models.TroubleshootingArticle).filter(models.TroubleshootingArticle.id == uid).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    return art


@router.put("/articles/{article_id}", response_model=schemas.TroubleshootingArticleOut)
async def update_article(
    article_id: str,
    update: schemas.TroubleshootingArticleUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    art = db.query(models.TroubleshootingArticle).filter(models.TroubleshootingArticle.id == uid).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(art, key, value)
    db.commit()
    db.refresh(art)
    return art


@router.post("/articles/{article_id}/success", response_model=schemas.TroubleshootingArticleOut)
async def mark_success(
    article_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(article_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid article id")
    art = db.query(models.TroubleshootingArticle).filter(models.TroubleshootingArticle.id == uid).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    art.success_count += 1
    db.commit()
    db.refresh(art)
    return art
