from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..models import AnalysisTool, InventoryItem
from ..schemas import AnalysisToolCreate, AnalysisToolOut, ToolRunIn
from ..tools import run_tool
from ..auth import get_current_user

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.post("", response_model=AnalysisToolOut)
def create_tool(tool: AnalysisToolCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    db_tool = AnalysisTool(**tool.model_dump(), created_by=user.id)
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool


@router.get("", response_model=list[AnalysisToolOut])
def list_tools(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(AnalysisTool).all()


@router.post("/{tool_id}/run")
def run_tool_endpoint(tool_id: UUID, data: ToolRunIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    tool = db.get(AnalysisTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404)
    item = db.get(InventoryItem, data.item_id)
    if not item:
        raise HTTPException(status_code=404)
    result = run_tool(tool.code, {"id": str(item.id), "type": item.item_type, "name": item.name, "custom_data": item.custom_data})
    return {"result": result}
