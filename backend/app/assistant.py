from datetime import datetime, timezone, timedelta
from sqlalchemy import or_
from sqlalchemy.orm import Session
from . import models


def generate_response(question: str, user: models.User, db: Session) -> str:
    q = question.lower()
    if "project" in q:
        projects = db.query(models.Project).all()
        names = ", ".join(p.name for p in projects) or "no projects"
        return f"Current projects: {names}."
    if "inventory" in q or "item" in q:
        items = db.query(models.InventoryItem).limit(5).all()
        names = ", ".join(i.name for i in items) or "no items"
        return f"Sample inventory items: {names}."
    return "I'm your lab buddy assistant. Ask me about projects or inventory."


def inventory_forecast(user: models.User, db: Session):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    items = db.query(models.InventoryItem).filter(models.InventoryItem.owner_id == user.id).all()
    results = []
    for item in items:
        stock = item.custom_data.get("stock") if isinstance(item.custom_data, dict) else None
        if stock is None:
            continue
        usage = (
            db.query(models.NotebookEntry)
            .filter(
                or_(
                    models.NotebookEntry.item_id == item.id,
                    models.NotebookEntry.items.contains([str(item.id)]),
                ),
                models.NotebookEntry.created_at >= since,
            )
            .count()
        )
        daily = usage / 30 if usage else 0
        days_left = stock / daily if daily else None
        results.append({"item_id": item.id, "name": item.name, "projected_days": days_left})
    return results


def suggest_protocols(goal: str, user: models.User, db: Session):
    q = f"%{goal.lower()}%"
    templates = (
        db.query(models.ProtocolTemplate)
        .filter(
            or_(
                models.ProtocolTemplate.name.ilike(q),
                models.ProtocolTemplate.content.ilike(q),
            )
        )
        .limit(3)
        .all()
    )
    suggestions = []
    for tpl in templates:
        materials = []
        for var in tpl.variables or []:
            item = (
                db.query(models.InventoryItem)
                .filter(
                    models.InventoryItem.owner_id == user.id,
                    or_(
                        models.InventoryItem.name.ilike(f"%{var}%"),
                        models.InventoryItem.item_type.ilike(f"%{var}%"),
                    ),
                )
                .first()
            )
            if item:
                materials.append({"id": item.id, "name": item.name})
        suggestions.append({
            "protocol_id": tpl.id,
            "protocol_name": tpl.name,
            "materials": materials,
        })
    return suggestions


def design_experiment(goal: str, user: models.User, db: Session):
    protocol = None
    suggestions = suggest_protocols(goal, user, db)
    if suggestions:
        protocol = suggestions[0]

    art_q = f"%{goal.lower()}%"
    articles = (
        db.query(models.KnowledgeArticle)
        .filter(
            or_(
                models.KnowledgeArticle.title.ilike(art_q),
                models.KnowledgeArticle.tags.contains([goal.lower()]),
            )
        )
        .limit(3)
        .all()
    )

    articles_out = [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "tags": a.tags,
            "created_by": a.created_by,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }
        for a in articles
    ]

    msg = "Suggested protocol and articles generated." if protocol or articles else "No suggestions found."
    return {"protocol": protocol, "articles": articles_out, "message": msg}
