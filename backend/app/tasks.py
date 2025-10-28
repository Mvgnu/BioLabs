import os
import datetime
from datetime import timezone
from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import joinedload
from uuid import UUID

from .database import SessionLocal
from .sequence import process_sequence_file
from .eventlog import record_execution_event
from .analytics.governance import invalidate_governance_analytics_cache
from . import models, notify

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
celery_app = Celery("tasks", broker=CELERY_BROKER_URL)
celery_app.conf.task_always_eager = (
    CELERY_BROKER_URL == "memory://" or os.getenv("TESTING") == "1"
)

@celery_app.task
def analyze_sequence_job(job_id: str, data: bytes, fmt: str):
    db = SessionLocal()
    job = db.get(models.SequenceAnalysisJob, UUID(job_id))
    if not job:
        db.close()
        return
    try:
        result = process_sequence_file(data, fmt)
        job.result = result
        job.status = "completed"
    except Exception:
        job.status = "failed"
        job.result = []
    db.commit()
    db.close()


def enqueue_analyze_sequence_job(job_id: str, data: bytes, fmt: str):
    if celery_app.conf.task_always_eager:
        analyze_sequence_job(job_id, data, fmt)
    else:
        analyze_sequence_job.delay(job_id, data, fmt)


celery_app.conf.beat_schedule = {
    "daily-backup": {
        "task": "app.tasks.backup_database",
        "schedule": crontab(hour=0, minute=0),
    },
    "inventory-warning": {
        "task": "app.tasks.check_inventory_levels",
        "schedule": crontab(hour=7, minute=0),
    },
    "narrative-approval-sla": {
        "task": "app.tasks.monitor_narrative_approval_slas",
        "schedule": crontab(minute="*/15"),
    },
}


@celery_app.task
def backup_database():
    dest = os.getenv("BACKUP_DIR", "/tmp/backups")
    os.makedirs(dest, exist_ok=True)
    fname = os.path.join(
        dest,
        f"backup_{datetime.datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}" + ".txt",
    )
    with open(fname, "w") as f:
        f.write("backup")
    return fname


@celery_app.task
def check_inventory_levels():
    from .assistant import inventory_forecast

    db = SessionLocal()
    threshold = int(os.getenv("INVENTORY_WARNING_DAYS", "7"))
    since = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)
    users = db.query(models.User).all()
    for user in users:
        forecasts = inventory_forecast(user, db)
        for f in forecasts:
            days = f.get("projected_days")
            if days is None or days > threshold:
                continue
            msg = f"{f['name']} may run out in {int(days)} days"
            exists = (
                db.query(models.Notification)
                .filter(
                    models.Notification.user_id == user.id,
                    models.Notification.message == msg,
                    models.Notification.created_at > since,
                )
                .first()
            )
            if exists:
                continue
            pref = (
                db.query(models.NotificationPreference)
                .filter_by(
                    user_id=user.id,
                    pref_type="inventory_alert",
                    channel="in_app",
                )
                .first()
            )
            if not pref or pref.enabled:
                db.add(models.Notification(user_id=user.id, message=msg))
            pref_email = (
                db.query(models.NotificationPreference)
                .filter_by(
                    user_id=user.id,
                    pref_type="inventory_alert",
                    channel="email",
                )
                .first()
            )
            if (not pref_email or pref_email.enabled) and user.email:
                notify.send_email(user.email, "Inventory Alert", msg)
    db.commit()
    db.close()


@celery_app.task
def monitor_narrative_approval_slas() -> None:
    """Identify overdue approval stages and emit lifecycle events."""

    db = SessionLocal()
    now = datetime.datetime.now(timezone.utc)
    try:
        overdue_stages = (
            db.query(models.ExecutionNarrativeApprovalStage)
            .options(
                joinedload(models.ExecutionNarrativeApprovalStage.export)
                .joinedload(models.ExecutionNarrativeExport.execution),
                joinedload(models.ExecutionNarrativeApprovalStage.export)
                .joinedload(models.ExecutionNarrativeExport.requested_by),
                joinedload(models.ExecutionNarrativeApprovalStage.assignee),
                joinedload(models.ExecutionNarrativeApprovalStage.delegated_to),
            )
            .filter(models.ExecutionNarrativeApprovalStage.status == "in_progress")
            .filter(models.ExecutionNarrativeApprovalStage.due_at.isnot(None))
            .filter(models.ExecutionNarrativeApprovalStage.due_at < now)
            .filter(models.ExecutionNarrativeApprovalStage.overdue_notified_at.is_(None))
            .all()
        )
        affected_execution_ids: set[UUID] = set()
        for stage in overdue_stages:
            stage.overdue_notified_at = now
            stage_meta = dict(stage.meta or {})
            stage_meta["overdue"] = True
            stage_meta["overdue_since"] = (
                stage.due_at.isoformat() if stage.due_at else now.isoformat()
            )
            stage.meta = stage_meta

            export = stage.export
            execution = export.execution if export else None
            escalation_actor = stage.assignee or stage.delegated_to
            if escalation_actor is None and export and export.requested_by:
                escalation_actor = export.requested_by

            recipients: list[models.User] = []
            if stage.assignee:
                recipients.append(stage.assignee)
            if stage.delegated_to and stage.delegated_to not in recipients:
                recipients.append(stage.delegated_to)

            notification_message = (
                f"Approval stage '{stage.name or stage.sequence_index}' for export {export.id if export else 'unknown'}"
                " is overdue."
            )
            notification_meta = {
                "export_id": str(export.id) if export else None,
                "stage_id": str(stage.id),
                "sequence_index": stage.sequence_index,
                "due_at": stage.due_at.isoformat() if stage.due_at else None,
            }
            for recipient in recipients:
                db.add(
                    models.Notification(
                        user_id=recipient.id,
                        message=notification_message,
                        title="Approval stage overdue",
                        category="compliance",
                        priority="urgent",
                        meta=notification_meta,
                    )
                )
                if getattr(recipient, "email", None):
                    notify.send_email(
                        recipient.email,
                        "Approval stage overdue",
                        notification_message,
                    )

            if export and export.execution_id:
                affected_execution_ids.add(export.execution_id)

            action_actor_id = None
            if escalation_actor:
                action_actor_id = escalation_actor.id
            elif export and export.requested_by_id:
                action_actor_id = export.requested_by_id
            elif recipients:
                action_actor_id = recipients[0].id

            if action_actor_id:
                escalation_action = models.ExecutionNarrativeApprovalAction(
                    stage_id=stage.id,
                    actor_id=action_actor_id,
                    action_type="escalated",
                    notes="Stage overdue SLA escalation",
                )
                escalation_action.meta = {
                    "due_at": stage.due_at.isoformat() if stage.due_at else None,
                    "escalated_at": now.isoformat(),
                }
                stage.actions.append(escalation_action)

            if execution:
                event_payload = {
                    "export_id": str(export.id) if export else None,
                    "stage_id": str(stage.id),
                    "sequence_index": stage.sequence_index,
                    "due_at": stage.due_at.isoformat() if stage.due_at else None,
                    "assignee_id": str(stage.assignee_id) if stage.assignee_id else None,
                    "delegate_id": str(stage.delegated_to_id) if stage.delegated_to_id else None,
                }
                record_execution_event(
                    db,
                    execution,
                    "narrative_export.approval.stage_overdue",
                    event_payload,
                )
                db.flush()
                record_execution_event(
                    db,
                    execution,
                    "narrative_export.approval.stage_escalated",
                    {
                        **event_payload,
                        "notified_user_ids": [str(user.id) for user in recipients],
                    },
                    actor=escalation_actor,
                )
        db.commit()
        if affected_execution_ids:
            invalidate_governance_analytics_cache(execution_ids=affected_execution_ids)
    finally:
        db.close()
