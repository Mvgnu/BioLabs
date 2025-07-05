from fastapi import APIRouter, Depends, UploadFile, File
import pandas as pd

from ..auth import get_current_user

router = APIRouter(prefix="/api/data", tags=["data"])

@router.post("/summary")
def csv_summary(upload: UploadFile = File(...), user=Depends(get_current_user)):
    df = pd.read_csv(upload.file)
    # return describe dictionary for numeric columns
    summary = df.describe().to_dict()
    return summary
