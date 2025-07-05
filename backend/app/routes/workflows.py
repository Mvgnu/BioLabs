from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas, tools

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("", response_model=schemas.WorkflowOut)
def create_workflow(wf: schemas.WorkflowCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    data = wf.model_dump()
    for step in data["steps"]:
        step["id"] = str(step["id"])
    db_wf = models.Workflow(**data, created_by=user.id)
    db.add(db_wf)
    db.commit()
    db.refresh(db_wf)
    return db_wf


@router.get("", response_model=list[schemas.WorkflowOut])
def list_workflows(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Workflow).all()


@router.post("/run", response_model=schemas.WorkflowExecutionOut)
def run_workflow(exec_in: schemas.WorkflowExecutionCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    wf = db.get(models.Workflow, exec_in.workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    item = db.get(models.InventoryItem, exec_in.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    results = []
    context = {"item": item, "results": results}
    for step in wf.steps:
        cond = step.get("condition")
        if cond:
            try:
                if not eval(cond, {}, context):
                    continue
            except Exception:
                continue
        if step.get("type") == "tool":
            tool_obj = db.get(models.AnalysisTool, UUID(step["id"]))
            if tool_obj:
                res = tools.run_tool(tool_obj.code, {
                    "id": str(item.id),
                    "type": item.item_type,
                    "name": item.name,
                    "custom_data": item.custom_data,
                })
                results.append(res)
                context["results"] = results
        elif step.get("type") == "protocol":
            tpl = db.get(models.ProtocolTemplate, UUID(step["id"]))
            if tpl:
                exec_db = models.ProtocolExecution(template_id=tpl.id, run_by=user.id, params={})
                db.add(exec_db)
                db.flush()
                results.append({"execution_id": str(exec_db.id)})
                context["results"] = results
    wf_exec = models.WorkflowExecution(
        workflow_id=wf.id,
        item_id=item.id,
        run_by=user.id,
        status="completed",
        result=results,
    )
    db.add(wf_exec)
    db.commit()
    db.refresh(wf_exec)
    return wf_exec


@router.get("/executions", response_model=list[schemas.WorkflowExecutionOut])
def list_executions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.WorkflowExecution).all()
