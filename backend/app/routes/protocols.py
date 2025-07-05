from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/protocols", tags=["protocols"])


@router.post("/templates", response_model=schemas.ProtocolTemplateOut)
async def create_template(
    template: schemas.ProtocolTemplateCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    version = 1
    existing = (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.name == template.name)
        .order_by(models.ProtocolTemplate.version.desc())
        .first()
    )
    if existing:
        try:
            version = int(existing.version) + 1
        except ValueError:
            version = 1
    db_template = models.ProtocolTemplate(
        **template.model_dump(), version=str(version), created_by=user.id
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.get("/templates", response_model=list[schemas.ProtocolTemplateOut])
async def list_templates(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return db.query(models.ProtocolTemplate).all()


@router.get("/public", response_model=list[schemas.ProtocolTemplateOut])
async def list_public_templates(db: Session = Depends(get_db)):
    return (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.is_public == True)
        .all()
    )


@router.put("/templates/{template_id}", response_model=schemas.ProtocolTemplateOut)
async def update_template(
    template_id: str,
    update: schemas.ProtocolTemplateUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == uid).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(tpl, key, value)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == uid).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tpl)
    db.commit()
    return {"detail": "deleted"}


@router.get(
    "/templates/{template_id}", response_model=schemas.ProtocolTemplateOut
)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == uid).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.post("/templates/{template_id}/star", response_model=schemas.ProtocolStarOut)
async def star_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        tid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == tid).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    existing = (
        db.query(models.ProtocolStar)
        .filter(models.ProtocolStar.protocol_id == tid, models.ProtocolStar.user_id == user.id)
        .first()
    )
    if existing:
        return existing
    star = models.ProtocolStar(protocol_id=tid, user_id=user.id)
    db.add(star)
    db.commit()
    db.refresh(star)
    return star


@router.delete("/templates/{template_id}/star")
async def unstar_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        tid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    star = (
        db.query(models.ProtocolStar)
        .filter(models.ProtocolStar.protocol_id == tid, models.ProtocolStar.user_id == user.id)
        .first()
    )
    if star:
        db.delete(star)
        db.commit()
    return {"detail": "ok"}


@router.get("/templates/{template_id}/stars")
async def get_template_stars(
    template_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        tid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    count = db.query(models.ProtocolStar).filter(models.ProtocolStar.protocol_id == tid).count()
    return {"count": count}


@router.post("/templates/{template_id}/fork", response_model=schemas.ProtocolTemplateOut)
async def fork_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == uid).first()
    if not tpl or not tpl.is_public:
        raise HTTPException(status_code=404, detail="Template not found or not public")
    member = db.query(models.TeamMember).filter(models.TeamMember.user_id == user.id).first()
    new_tpl = models.ProtocolTemplate(
        name=tpl.name,
        content=tpl.content,
        variables=tpl.variables,
        is_public=False,
        forked_from=tpl.id,
        team_id=member.team_id if member else None,
        created_by=user.id,
    )
    db.add(new_tpl)
    db.commit()
    db.refresh(new_tpl)
    return new_tpl


@router.post("/executions", response_model=schemas.ProtocolExecutionOut)
async def create_execution(
    execution: schemas.ProtocolExecutionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        tpl_id = UUID(str(execution.template_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template id")
    tpl = (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.id == tpl_id)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tpl.variables:
        missing = [v for v in tpl.variables if v not in execution.params]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing params: {', '.join(missing)}")
    db_exec = models.ProtocolExecution(
        template_id=tpl_id,
        run_by=user.id,
        params=execution.params,
        status="pending",
    )
    db.add(db_exec)
    db.commit()
    db.refresh(db_exec)
    return db_exec


@router.get("/executions", response_model=list[schemas.ProtocolExecutionOut])
async def list_executions(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return db.query(models.ProtocolExecution).all()


@router.get("/executions/{exec_id}", response_model=schemas.ProtocolExecutionOut)
async def get_execution(
    exec_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(exec_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution id")
    exec_db = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == uid)
        .first()
    )
    if not exec_db:
        raise HTTPException(status_code=404, detail="Execution not found")
    return exec_db


@router.put("/executions/{exec_id}", response_model=schemas.ProtocolExecutionOut)
async def update_execution(
    exec_id: str,
    update: schemas.ProtocolExecutionUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(exec_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution id")
    exec_db = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == uid)
        .first()
    )
    if not exec_db:
        raise HTTPException(status_code=404, detail="Execution not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(exec_db, key, value)
    db.commit()
    db.refresh(exec_db)
    return exec_db


# ----- Merge Requests -----

@router.post("/merge-requests", response_model=schemas.ProtocolMergeRequestOut)
async def create_merge_request(
    req: schemas.ProtocolMergeRequestCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == req.template_id).first()
    if not tpl or not tpl.is_public:
        raise HTTPException(status_code=404, detail="Template not found or not public")
    mr = models.ProtocolMergeRequest(
        template_id=req.template_id,
        proposer_id=user.id,
        content=req.content,
        variables=req.variables,
    )
    db.add(mr)
    db.commit()
    db.refresh(mr)
    return mr


@router.get("/diff")
async def diff_templates(
    old_id: str,
    new_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        oid = UUID(old_id)
        nid = UUID(new_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    old = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == oid).first()
    new = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == nid).first()
    if not old or not new:
        raise HTTPException(status_code=404, detail="Template not found")
    import difflib
    diff = "\n".join(
        difflib.unified_diff(
            old.content.splitlines(),
            new.content.splitlines(),
            fromfile=str(old.id),
            tofile=str(new.id),
        )
    )
    return {"diff": diff}


@router.get("/merge-requests", response_model=list[schemas.ProtocolMergeRequestOut])
async def list_merge_requests(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.ProtocolMergeRequest)
        .join(models.ProtocolTemplate, models.ProtocolMergeRequest.template_id == models.ProtocolTemplate.id)
        .filter(models.ProtocolTemplate.created_by == user.id)
        .all()
    )


def _get_merge_request(db: Session, mr_id: UUID) -> models.ProtocolMergeRequest:
    mr = db.query(models.ProtocolMergeRequest).filter(models.ProtocolMergeRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Merge request not found")
    return mr


@router.post("/merge-requests/{mr_id}/accept", response_model=schemas.ProtocolTemplateOut)
async def accept_merge_request(
    mr_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(mr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merge request id")
    mr = _get_merge_request(db, uid)
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == mr.template_id).first()
    if tpl.created_by != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    tpl.content = mr.content
    tpl.variables = mr.variables
    mr.status = "accepted"
    db.commit()
    db.refresh(tpl)
    return tpl


@router.post("/merge-requests/{mr_id}/reject", response_model=schemas.ProtocolMergeRequestOut)
async def reject_merge_request(
    mr_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        uid = UUID(mr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merge request id")
    mr = _get_merge_request(db, uid)
    tpl = db.query(models.ProtocolTemplate).filter(models.ProtocolTemplate.id == mr.template_id).first()
    if tpl.created_by != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    mr.status = "rejected"
    db.commit()
    db.refresh(mr)
    return mr
