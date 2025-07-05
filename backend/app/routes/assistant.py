from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas
from ..assistant import (
    generate_response,
    inventory_forecast,
    suggest_protocols,
    design_experiment,
)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

@router.post("/ask", response_model=schemas.AssistantMessageOut)
def ask_question(
    question: schemas.AssistantQuestion,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    user_msg = models.AssistantMessage(user_id=user.id, is_user=True, message=question.question)
    db.add(user_msg)
    db.flush()
    answer = generate_response(question.question, user, db)
    bot_msg = models.AssistantMessage(user_id=user.id, is_user=False, message=answer)
    db.add(bot_msg)
    db.commit()
    db.refresh(bot_msg)
    return bot_msg


@router.get("", response_model=list[schemas.AssistantMessageOut])
def get_history(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    msgs = (
        db.query(models.AssistantMessage)
        .filter(models.AssistantMessage.user_id == user.id)
        .order_by(models.AssistantMessage.created_at)
        .all()
    )
    return msgs


@router.get("/forecast", response_model=list[schemas.InventoryForecastItem])
def get_inventory_forecast(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return inventory_forecast(user, db)


@router.get("/suggest", response_model=list[schemas.ProtocolSuggestion])
def suggest_protocol(
    goal: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return suggest_protocols(goal, user, db)


@router.get("/design", response_model=schemas.ExperimentDesignOut)
def design_experiment_endpoint(
    goal: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return design_experiment(goal, user, db)
