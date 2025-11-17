from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from .. import models, schemas
from ..database import get_db
from ..services import billing as billing_service
from ..sequence import (
    process_sequence_file,
    align_sequences,
    design_primers,
    restriction_map,
    parse_genbank_features,
    parse_chromatogram,
    blast_search,
)
from ..tasks import enqueue_analyze_sequence_job
from uuid import UUID

router = APIRouter(prefix="/api/sequence", tags=["sequence"])

@router.post("/analyze", response_model=list[schemas.SequenceRead])
async def analyze_sequence(
    format: str = Form("fasta"),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    data = await upload.read()
    try:
        return process_sequence_file(data, format)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid sequence file")


@router.post("/align", response_model=schemas.SequenceAlignmentOut)
async def align(
    payload: schemas.SequenceAlignmentIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return align_sequences(payload.seq1, payload.seq2, payload.mode)


@router.post("/blast", response_model=schemas.BlastSearchOut)
async def blast(
    payload: schemas.BlastSearchIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return blast_search(payload.query, payload.subject)


@router.post("/primers", response_model=schemas.PrimerDesignOut)
async def primers(
    payload: schemas.PrimerDesignIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        return design_primers(payload.sequence, payload.size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/restriction", response_model=schemas.RestrictionMapOut)
async def restriction(
    payload: schemas.RestrictionMapIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        mapping = restriction_map(payload.sequence, payload.enzymes)
        return {"map": mapping}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid input")


@router.post("/annotate", response_model=list[schemas.SequenceFeature])
async def annotate(
    format: str = Form("genbank"),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    data = await upload.read()
    try:
        if format not in {"genbank", "gb"}:
            raise ValueError("Unsupported format")
        return parse_genbank_features(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid annotation file")


@router.post("/chromatogram", response_model=schemas.ChromatogramOut)
async def chromatogram(
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    data = await upload.read()
    try:
        return parse_chromatogram(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid chromatogram file")


@router.post("/jobs", response_model=schemas.SequenceJobOut)
async def create_analysis_job(
    format: str = Form("fasta"),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    data = await upload.read()
    job = models.SequenceAnalysisJob(user_id=user.id, format=format, result=None)
    db.add(job)
    db.flush()
    _emit_sequence_usage_event(db, user, job)
    db.commit()
    db.refresh(job)
    enqueue_analyze_sequence_job(str(job.id), data, format)
    return job


@router.get("/jobs", response_model=list[schemas.SequenceJobOut])
async def list_analysis_jobs(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    jobs = (
        db.query(models.SequenceAnalysisJob)
        .filter(models.SequenceAnalysisJob.user_id == user.id)
        .order_by(models.SequenceAnalysisJob.created_at.desc())
        .all()
    )
    return jobs


@router.get("/jobs/{job_id}", response_model=schemas.SequenceJobOut)
async def get_analysis_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    job = (
        db.query(models.SequenceAnalysisJob)
        .filter(
            models.SequenceAnalysisJob.id == job_uuid,
            models.SequenceAnalysisJob.user_id == user.id,
        )
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _emit_sequence_usage_event(db: Session, user: models.User, job: models.SequenceAnalysisJob) -> None:
    team_id, organization_id = _resolve_user_team_scope(db, user)
    if not organization_id:
        return
    try:
        billing_service.record_usage_event(
            db,
            schemas.MarketplaceUsageEventCreate(
                organization_id=organization_id,
                team_id=team_id,
                user_id=user.id,
                service="analytics",
                operation="sequence_analysis_job",
                unit_quantity=1.0,
                credits_consumed=5,
                guardrail_flags=[],
                metadata={"job_id": str(job.id), "format": job.format},
            ),
        )
    except billing_service.SubscriptionNotFound:
        return


def _resolve_user_team_scope(db: Session, user: models.User) -> tuple[UUID | None, UUID | None]:
    membership = (
        db.query(models.TeamMember)
        .join(models.Team)
        .filter(models.TeamMember.user_id == user.id)
        .filter(models.Team.organization_id.isnot(None))
        .order_by(models.Team.created_at.asc())
        .first()
    )
    if membership and membership.team and membership.team.organization_id:
        return membership.team.id, membership.team.organization_id
    return None, None
