from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..models import (
    Project,
    ProjectMember,
    ProjectItem,
    ProjectProtocol,
    ProjectTask,
)
from ..schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectOut,
    ProjectTaskCreate,
    ProjectTaskUpdate,
    ProjectTaskOut,
)
from ..auth import get_current_user
from ..rbac import ensure_project_member

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    db_proj = Project(**project.model_dump(), created_by=user.id)
    db.add(db_proj)
    db.flush()
    db.add(ProjectMember(project_id=db_proj.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(db_proj)
    return db_proj


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Project).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(status_code=404)
    return proj


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: UUID,
    project: ProjectUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(status_code=404)
    ensure_project_member(db, user, project_id, ("owner",))
    for k, v in project.model_dump(exclude_unset=True).items():
        setattr(proj, k, v)
    db.commit()
    db.refresh(proj)
    return proj


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(status_code=404)
    ensure_project_member(db, user, project_id, ("owner",))
    db.query(ProjectMember).filter_by(project_id=project_id).delete()
    db.query(ProjectItem).filter_by(project_id=project_id).delete()
    db.query(ProjectProtocol).filter_by(project_id=project_id).delete()
    db.delete(proj)
    db.commit()
    return Response(status_code=204)


@router.post("/{project_id}/items", status_code=204)
def add_project_item(project_id: UUID, item_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_project_member(db, user, project_id)
    db.add(ProjectItem(project_id=project_id, item_id=item_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{project_id}/protocols", status_code=204)
def add_project_protocol(project_id: UUID, template_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_project_member(db, user, project_id)
    db.add(ProjectProtocol(project_id=project_id, template_id=template_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{project_id}/members", status_code=204)
def add_project_member(project_id: UUID, member_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_project_member(db, user, project_id, ("owner",))
    db.add(ProjectMember(project_id=project_id, user_id=member_id, role="member"))
    db.commit()
    return Response(status_code=204)


@router.get("/{project_id}/tasks", response_model=list[ProjectTaskOut])
def list_project_tasks(project_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_project_member(db, user, project_id)
    return db.query(ProjectTask).filter_by(project_id=project_id).all()


@router.post("/{project_id}/tasks", response_model=ProjectTaskOut)
def create_project_task(
    project_id: UUID,
    task: ProjectTaskCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ensure_project_member(db, user, project_id)
    db_task = ProjectTask(
        **task.model_dump(), project_id=project_id, created_by=user.id
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.put("/{project_id}/tasks/{task_id}", response_model=ProjectTaskOut)
def update_project_task(
    project_id: UUID,
    task_id: UUID,
    data: ProjectTaskUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    task = db.get(ProjectTask, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404)
    ensure_project_member(db, user, project_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
def delete_project_task(project_id: UUID, task_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = db.get(ProjectTask, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404)
    ensure_project_member(db, user, project_id)
    db.delete(task)
    db.commit()
    return Response(status_code=204)
